import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from utils.codebuddy_database import DB_PATH
from utils.codebuddy_database import (
    add_guild_save_units,
    get_guild_save_units,
    get_user_save_units,
    increment_quest_counting_count,
    try_use_guild_save,
    try_use_user_save,
)
import ast
import operator
import math
import asyncio
import time
from typing import Optional

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cache for counting channels: guild_id -> channel_id
        self.counting_channels = {}
        # Protect against occasional duplicate MESSAGE_CREATE dispatches or accidental double-processing.
        # Key: message_id, Value: monotonic timestamp
        self._recent_message_ids: dict[int, float] = {}
        # Throttle reaction API calls to avoid Discord rate limits in fast counting channels.
        self._reaction_queue: asyncio.Queue[tuple[discord.Message, str]] = asyncio.Queue()
        self._pending_reactions: set[tuple[int, str]] = set()
        self._reaction_worker_task: Optional[asyncio.Task[None]] = None

    async def cog_unload(self) -> None:
        if self._reaction_worker_task and not self._reaction_worker_task.done():
            self._reaction_worker_task.cancel()

    async def _reaction_worker(self) -> None:
        # A small delay between reaction requests keeps us under the common reaction route limits.
        # Reactions may appear slightly delayed, but they will still be added.
        while True:
            message, emoji = await self._reaction_queue.get()
            try:
                try:
                    await message.add_reaction(emoji)
                except Exception:
                    pass
                await asyncio.sleep(0.35)
            finally:
                self._pending_reactions.discard((message.id, emoji))
                self._reaction_queue.task_done()

    def _enqueue_reaction(self, message: discord.Message, emoji: str) -> None:
        key = (message.id, emoji)
        if key in self._pending_reactions:
            return
        self._pending_reactions.add(key)
        try:
            self._reaction_queue.put_nowait((message, emoji))
        except Exception:
            self._pending_reactions.discard(key)

    async def cog_load(self):
        """Load counting channels into memory on startup"""
        if self._reaction_worker_task is None or self._reaction_worker_task.done():
            self._reaction_worker_task = asyncio.create_task(self._reaction_worker())
        try:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                # Ensure auxiliary tables exist
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS counting_warnings (
                        guild_id INTEGER,
                        user_id INTEGER,
                        warnings INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS counting_active_highscore (
                        guild_id INTEGER PRIMARY KEY,
                        message_id INTEGER
                    )
                """)

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS counting_highscore_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        score INTEGER NOT NULL,
                        user_id INTEGER,
                        message_id INTEGER,
                        timestamp INTEGER
                    )
                """)

                await db.commit()

                try:
                    async with db.execute("SELECT guild_id, channel_id FROM counting_config") as cursor:
                        rows = await cursor.fetchall()
                        for guild_id, channel_id in rows:
                            self.counting_channels[guild_id] = channel_id
                    print(f"Loaded {len(self.counting_channels)} counting channels")
                except aiosqlite.OperationalError:
                    print("counting_config table not found during cog load (likely first run)")
        except Exception as e:
            print(f"Error loading counting channels: {e}")

    async def _get_warning_count(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute(
                "SELECT warnings FROM counting_warnings WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def _set_warning_count(self, guild_id: int, user_id: int, warnings: int) -> None:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            if warnings <= 0:
                await db.execute(
                    "DELETE FROM counting_warnings WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO counting_warnings (guild_id, user_id, warnings)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET warnings = excluded.warnings
                    """,
                    (guild_id, user_id, warnings),
                )
            await db.commit()

    async def _clear_all_warnings(self, guild_id: int) -> None:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            await db.execute("DELETE FROM counting_warnings WHERE guild_id = ?", (guild_id,))
            await db.commit()

    async def _get_active_highscore_message_id(self, guild_id: int) -> Optional[int]:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute(
                "SELECT message_id FROM counting_active_highscore WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else None

    async def _set_active_highscore_message_id(self, guild_id: int, message_id: Optional[int]) -> None:
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            if message_id is None:
                await db.execute("DELETE FROM counting_active_highscore WHERE guild_id = ?", (guild_id,))
            else:
                await db.execute(
                    """
                    INSERT INTO counting_active_highscore (guild_id, message_id)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET message_id = excluded.message_id
                    """,
                    (guild_id, message_id),
                )
            await db.commit()

    async def _remove_bot_reactions(self, channel: discord.TextChannel, message_id: int) -> None:
        try:
            msg = await channel.fetch_message(message_id)
        except Exception:
            return

        if not self.bot.user:
            return
        try:
            await msg.remove_reaction("✅", self.bot.user)
        except Exception:
            pass
        try:
            await msg.remove_reaction("🏆", self.bot.user)
        except Exception:
            pass

    async def _mark_highscore_message(
        self,
        message: discord.Message,
        new_count: int,
        previous_high_score: int,
    ) -> None:
        """Add ✅+🏆 to the message.

        Note: Reactions, once added by the bot, should never be removed.
        """
        if not message.guild or not isinstance(message.channel, discord.TextChannel):
            return

        guild_id = message.guild.id
        channel = message.channel

        # Only add the trophy here.
        # The ✅ reaction is added for all valid counts in the main handler;
        # adding it again here causes extra API calls and rate limits.
        self._enqueue_reaction(message, "🏆")

        # Track the latest highscore/tie message ID for bookkeeping.
        # (We no longer remove reactions from older messages.)
        await self._set_active_highscore_message_id(guild_id, message.id)

        # Record history only if it is a NEW record
        if new_count > previous_high_score:
            async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                await db.execute(
                    """
                    INSERT INTO counting_highscore_history (guild_id, score, user_id, message_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (guild_id, new_count, message.author.id, message.id, int(time.time())),
                )
                await db.commit()

    async def _clear_highscore_marker_if_any(self, guild_id: int, channel: discord.TextChannel) -> None:
        marker_id = await self._get_active_highscore_message_id(guild_id)
        if marker_id:
            await self._set_active_highscore_message_id(guild_id, None)

    @app_commands.command(name="setcountingchannel", description="Set the channel for the counting game")
    @app_commands.checks.has_permissions(administrator=True)
    async def setcountingchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Slash command interactions must be acknowledged quickly.
        # DB operations can take >3s (locks, slow disks), so defer immediately.
        if interaction.response.is_done():
            # Extremely defensive; normally false here.
            pass
        else:
            await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        retries = 3
        while retries > 0:
            try:
                async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                    await db.execute(
                        """
                        INSERT INTO counting_config (guild_id, channel_id)
                        VALUES (?, ?)
                        ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
                        """,
                        (interaction.guild_id, channel.id),
                    )
                    await db.commit()
                break
            except aiosqlite.OperationalError as e:
                if "locked" in str(e).lower():
                    retries -= 1
                    await asyncio.sleep(0.5)
                    continue
                raise

        # Update cache
        self.counting_channels[interaction.guild_id] = channel.id

        await interaction.followup.send(f"Counting channel set to {channel.mention}", ephemeral=True)

    def safe_eval(self, expr):
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.BitXor: operator.pow, # Allow ^ for power
            ast.USub: operator.neg
        }

        constants = {
            "e": math.e,
            "pi": math.pi,
            "tau": math.tau,
        }

        functions = {
            "log": math.log,
            "log10": math.log10,
            "sqrt": math.sqrt,
            "factorial": math.factorial,
            "ceil": math.ceil,
            "floor": math.floor,
            "trunc": math.trunc,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "acos": math.acos,
            "atan": math.atan,
            "degrees": math.degrees,
            "radians": math.radians,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "asinh": math.asinh,
            "acosh": math.acosh,
            "atanh": math.atanh,
        }

        def eval_node(node):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise TypeError("Not a number")
            elif isinstance(node, ast.BinOp):
                op = type(node.op)
                if op in operators:
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    if op in (ast.Pow, ast.BitXor):
                        if right > 100: # Limit exponent
                            raise ValueError("Exponent too large")
                    return operators[op](left, right)
            elif isinstance(node, ast.UnaryOp):
                op = type(node.op)
                if op in operators:
                    return operators[op](eval_node(node.operand))
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in functions:
                        args = [eval_node(a) for a in node.args]
                        return functions[node.func.id](*args)
                    
            elif isinstance(node, ast.Name):
                if node.id in constants:
                    return constants[node.id]
                raise TypeError(f"Unknown identifier {node.id}")
            raise TypeError("Unsupported type")

        try:
            tree = ast.parse(expr, mode='eval')
            return eval_node(tree.body)
        except Exception:
            return None

    def _extract_leading_expression(self, text: str) -> Optional[str]:
        """Extract a safe-eval compatible expression from the start of a message.

        This allows messages like "43 is next" or "6*7 nice" to count as 43/42.
        Only a leading run of digits/operators/parentheses is considered.
        """
        if not text:
            return None

        # Normalize whitespace/newlines.
        s = text.replace("\n", " ").strip()
        if not s:
            return None

        # Allow common markdown wrappers before the number (e.g. `43`, **43**).
        s = s.lstrip()
        while s and s[0] in "`*_~":
            s = s[1:].lstrip()

        allowed = set("0123456789+-*/^(). ")
        expr_chars: list[str] = []
        for ch in s:
            if ch in allowed:
                expr_chars.append(ch)
            else:
                break

        expr = "".join(expr_chars).strip()
        return expr or None

    def _parse_count_number(self, message_content: str) -> Optional[int]:
        expr = self._extract_leading_expression(message_content)
        if not expr:
            return None

        number = self.safe_eval(expr)
        if number is None:
            return None

        if isinstance(number, float):
            if number.is_integer():
                return int(number)
            return None
        if isinstance(number, int):
            return number
        return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # 1. OPTIMIZATION: Check cache first before touching DB
        if message.guild.id not in self.counting_channels:
            return
        
        if message.channel.id != self.counting_channels[message.guild.id]:
            return

        # Deduplicate processing of the same message ID within this process.
        # This prevents duplicate warnings/messages if Discord or the bot dispatches the event twice.
        now = time.monotonic()
        last_seen = self._recent_message_ids.get(message.id)
        if last_seen is not None and (now - last_seen) < 30:
            return
        self._recent_message_ids[message.id] = now
        if len(self._recent_message_ids) > 5000:
            cutoff = now - 120
            self._recent_message_ids = {mid: ts for mid, ts in self._recent_message_ids.items() if ts >= cutoff}

        # 2. Process the message logic
        # Wrap DB operations in retry loop for robustness
        retries = 3
        while retries > 0:
            try:
                async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                    async with db.execute("SELECT current_count, last_user_id, high_score FROM counting_config WHERE guild_id = ?", (message.guild.id,)) as cursor:
                        config = await cursor.fetchone()
                    
                    if not config:
                        # Should not happen if in cache, but possible if DB was manually cleared
                        return

                    current_count, last_user_id, high_score = config

                    # Try to parse the number
                    content = message.content.strip()
                    if not content:
                        return

                    # Evaluate math expression (supports extra trailing text like "43 is next")
                    number = self._parse_count_number(content)
                    if number is None:
                        return  # Not a valid number/expression at the start

                    # Check rules
                    next_count = current_count + 1
                    
                    if number != next_count:
                        await self.fail_count(message, current_count, "Wrong number!")
                        return

                    if message.author.id == last_user_id:
                        # Warn instead of instant ruin. 3 warnings ruins the count.
                        # Use an atomic increment in the SAME connection to avoid races and DB-lock retries.
                        await db.execute(
                            """
                            INSERT INTO counting_warnings (guild_id, user_id, warnings)
                            VALUES (?, ?, 1)
                            ON CONFLICT(guild_id, user_id) DO UPDATE SET warnings = warnings + 1
                            """,
                            (message.guild.id, message.author.id),
                        )
                        async with db.execute(
                            "SELECT warnings FROM counting_warnings WHERE guild_id = ? AND user_id = ?",
                            (message.guild.id, message.author.id),
                        ) as cursor:
                            row = await cursor.fetchone()
                        warnings = int(row[0]) if row else 1
                        await db.commit()

                        if warnings >= 3:
                            await self.fail_count(message, current_count, "Too many warnings (counted twice in a row 3 times)!")
                            return

                        self._enqueue_reaction(message, "⚠️")

                        await message.channel.send(
                            f"You can't count twice in a row, {message.author.mention}. "
                            f"You have **{warnings}/3** warnings.",
                            delete_after=12,
                        )
                        return

                    # Valid count - Update DB
                    new_high_score = max(high_score, next_count)
                    
                    # Update configuration tables
                    await db.execute("""
                        UPDATE counting_config 
                        SET current_count = ?, last_user_id = ?, high_score = ?
                        WHERE guild_id = ?
                    """, (next_count, message.author.id, new_high_score, message.guild.id))
                    
                    # Update user stats
                    await db.execute("""
                        INSERT INTO counting_stats (user_id, guild_id, total_counts, ruined_counts)
                        VALUES (?, ?, 1, 0)
                        ON CONFLICT(user_id, guild_id) DO UPDATE SET total_counts = total_counts + 1
                    """, (message.author.id, message.guild.id))

                    # Reset warnings for this user on a valid count (in the same transaction).
                    await db.execute(
                        "DELETE FROM counting_warnings WHERE guild_id = ? AND user_id = ?",
                        (message.guild.id, message.author.id),
                    )
                    
                    await db.commit()

                    # Side effects after commit to avoid duplicate reactions on retries.
                    self._enqueue_reaction(message, "✅")

                    # Daily quest progress: count 5 numbers (best-effort).
                    try:
                        quest_completed = await increment_quest_counting_count(message.author.id)
                        if quest_completed:
                            await message.channel.send(
                                f"Daily quest completed, {message.author.mention}! "
                                "You earned **0.2** Streak Freeze and **0.5** Save. "
                                "Use `?inventory` to check your items.",
                                delete_after=15,
                            )
                    except Exception:
                        pass

                    # Highscore marker: react ✅+🏆 when reaching/topping the record
                    if next_count >= high_score:
                        await self._mark_highscore_message(message, next_count, high_score)
                    return # Success
            
            except aiosqlite.OperationalError as e:
                # If specifically locked, retry
                if "locked" in str(e):
                    retries -= 1
                    if retries == 0:
                        print(f"Database locked repeatedly in counting for msg {message.id}")
                        # Don't crash bot, just ignore or log
                        return
                    await asyncio.sleep(0.1 * (4 - retries)) # backoff
                else:
                    raise # Re-raise other operational errors

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Announce when someone deletes a counting number message."""
        if message.author.bot or not message.guild:
            return

        if message.guild.id not in self.counting_channels:
            return

        if message.channel.id != self.counting_channels[message.guild.id]:
            return

        content = (message.content or "").strip()
        if not content:
            return

        number = self._parse_count_number(content)
        if number is None:
            return

        await message.channel.send(
            f"{message.author.mention} deleted a number **{number}**.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    async def fail_count(self, message, current_count, reason):
        # Replace dice mechanic with save mechanic:
        # 1) Use a personal save if available.
        # 2) Else use a guild save if available.
        # 3) Else the count is ruined (reset to 0).

        try:
            await message.add_reaction("❌")
        except Exception:
            pass

        if not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # Clear this user's warnings so a saved mistake doesn't soft-lock them.
        try:
            await self._set_warning_count(guild_id, user_id, 0)
        except Exception:
            pass

        used_personal = False
        used_guild = False
        try:
            used_personal = await try_use_user_save(user_id)
        except Exception:
            used_personal = False

        # Only spend a server save with explicit confirmation.
        if not used_personal:
            guild_units = 0
            try:
                guild_units = await get_guild_save_units(guild_id)
            except Exception:
                guild_units = 0

            if guild_units >= 10:
                prompt_msg: Optional[discord.Message] = None
                try:
                    prompt_msg = await message.channel.send(
                        f"{message.author.mention} do you want to waste a server save for your foolish ruin?"
                    )
                except Exception:
                    prompt_msg = None

                if prompt_msg is not None:
                    try:
                        await prompt_msg.add_reaction("✅")
                        await prompt_msg.add_reaction("❌")
                    except Exception:
                        pass

                    def _check(reaction: discord.Reaction, user: discord.abc.User) -> bool:
                        if user.bot:
                            return False
                        if user.id != message.author.id:
                            return False
                        if reaction.message.id != prompt_msg.id:
                            return False
                        return str(reaction.emoji) in {"✅", "❌"}

                    try:
                        reaction, _user = await self.bot.wait_for(
                            "reaction_add", timeout=20.0, check=_check
                        )
                        if str(reaction.emoji) == "✅":
                            try:
                                used_guild = await try_use_guild_save(guild_id)
                            except Exception:
                                used_guild = False
                        else:
                            used_guild = False
                    except asyncio.TimeoutError:
                        used_guild = False
                    except Exception:
                        used_guild = False

        if used_personal or used_guild:
            try:
                remaining_user_units = await get_user_save_units(user_id)
            except Exception:
                remaining_user_units = 0
            try:
                remaining_guild_units = await get_guild_save_units(guild_id)
            except Exception:
                remaining_guild_units = 0

            source = "your" if used_personal else "the server's"
            await message.channel.send(
                f"{reason} {message.author.mention} messed up at **{current_count}**, "
                f"but {source} save was used — the count is **saved**.\n"
                f"Next number is **{current_count + 1}**.\n"
                f"Your saves: **{remaining_user_units/10:.1f}** • Server saves: **{remaining_guild_units/10:.1f}**"
            )
            return

        # No saves: ruin the count (reset to 0)
        db_ops = [
            (
                """
                UPDATE counting_config
                SET current_count = 0, last_user_id = NULL
                WHERE guild_id = ?
                """,
                (guild_id,),
            ),
            (
                """
                INSERT INTO counting_stats (user_id, guild_id, total_counts, ruined_counts)
                VALUES (?, ?, 0, 1)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET ruined_counts = ruined_counts + 1
                """,
                (user_id, guild_id),
            ),
        ]

        retries = 3
        while retries > 0:
            try:
                async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
                    for sql, args in db_ops:
                        await db.execute(sql, args)
                    await db.commit()
                break
            except aiosqlite.OperationalError as e:
                if "locked" in str(e).lower():
                    retries -= 1
                    await asyncio.sleep(0.3)
                    continue
                break

        await message.channel.send(
            f"{reason} {message.author.mention} messed up at **{current_count}**. "
            "No saves were available — the count is **ruined** and has been reset to **0**.\n"
            "Next number is **1**."
        )

        if isinstance(message.channel, discord.TextChannel):
            await self._clear_all_warnings(guild_id)
            await self._clear_highscore_marker_if_any(guild_id, message.channel)


    @commands.command(name="donateguild", aliases=["dg"])
    async def donate_guild(self, ctx: commands.Context):
        """Donate 1 personal save to the guild pool (guild receives 0.5 save)."""
        if not ctx.guild:
            return await ctx.send("Server only command.")

        user_id = ctx.author.id
        guild_id = ctx.guild.id

        # Need at least 1.0 save (10 units) to donate.
        user_units = await get_user_save_units(user_id)
        if user_units < 10:
            return await ctx.send(
                f"You need **1.0** save to donate. Your saves: **{user_units/10:.1f}**"
            )

        # Consume 1.0 personal save
        used = await try_use_user_save(user_id)
        if not used:
            return await ctx.send("Couldn't donate right now (try again).")

        # Guild receives 0.5 save (5 units)
        await add_guild_save_units(guild_id, 5)

        new_user_units = await get_user_save_units(user_id)
        new_guild_units = await get_guild_save_units(guild_id)
        await ctx.send(
            f"Donated **1.0** save to the server pool. Server gained **0.5** save.\n"
            f"Your saves: **{new_user_units/10:.1f}** • Server saves: **{new_guild_units/10:.1f}**"
        )


    @commands.command(name="guildsaves", aliases=["gsaves", "serversaves", "ssaves"])
    async def guild_saves(self, ctx: commands.Context):
        """Show the server save pool used to protect counting mistakes."""
        if not ctx.guild:
            return await ctx.send("Server only command.")

        units = await get_guild_save_units(ctx.guild.id)
        await ctx.send(
            f"Server saves: **{units/10:.1f}**\n"
            "(Needs **1.0** server save to protect a ruined count.)"
        )

    @commands.hybrid_command(name="highscoretable", aliases=["highscores"], help="Show recent counting highscores")
    async def highscore_table(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.send("Server only command.")

        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute(
                """
                SELECT score, user_id, timestamp
                FROM counting_highscore_history
                WHERE guild_id = ?
                ORDER BY score DESC
                LIMIT 10
                """,
                (ctx.guild.id,),
            ) as cursor:
                rows = await cursor.fetchall()

            async with db.execute(
                "SELECT current_count, high_score FROM counting_config WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                config = await cursor.fetchone()

        current = config[0] if config else 0
        high = config[1] if config else 0

        embed = discord.Embed(title="Counting Highscores", color=discord.Color.gold())
        embed.add_field(name="Current Count", value=str(current), inline=True)
        embed.add_field(name="All-Time High", value=str(high), inline=True)

        if not rows:
            embed.description = "No highscore history yet."
            return await ctx.send(embed=embed)

        lines = []
        for i, (score, user_id, ts) in enumerate(rows, 1):
            when = f"<t:{int(ts)}:R>" if ts else ""
            lines.append(f"{i}. **{score}** by <@{user_id}> {when}")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

    @commands.command(name="mcl", aliases=["tc"])
    async def most_count_leaderboard(self, ctx):
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute("""
                SELECT user_id, total_counts 
                FROM counting_stats 
                WHERE guild_id = ? 
                ORDER BY total_counts DESC 
                LIMIT 10
            """, (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No counting stats yet.")
            return

        embed = discord.Embed(title="Most Count Leaderboard", color=discord.Color.blue())
        description = ""
        for i, (user_id, count) in enumerate(rows, 1):
            description += f"{i}. <@{user_id}>: {count}\n"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(name="mrl")
    async def most_ruined_leaderboard(self, ctx):
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute("""
                SELECT user_id, ruined_counts 
                FROM counting_stats 
                WHERE guild_id = ? 
                ORDER BY ruined_counts DESC 
                LIMIT 10
            """, (ctx.guild.id,)) as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("No ruined stats yet.")
            return

        embed = discord.Embed(title="Most Ruined Leaderboard", color=discord.Color.red())
        description = ""
        for i, (user_id, count) in enumerate(rows, 1):
            description += f"{i}. <@{user_id}>: {count}\n"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(name="scs")
    async def server_count_stats(self, ctx):
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
            async with db.execute("SELECT current_count, high_score FROM counting_config WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            await ctx.send("Counting channel not set up or no data.")
            return
            
        current, high = row
        embed = discord.Embed(title="Server Count Stats", color=discord.Color.green())
        embed.add_field(name="Current Count", value=str(current))
        embed.add_field(name="High Score", value=str(high))
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Counting(bot))
