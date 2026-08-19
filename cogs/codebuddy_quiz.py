import os
import random
import time
from typing import TypedDict, cast

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.codebuddy_database import (
    get_leaderboard,
    get_score_gap,
    get_user_rank,
    get_user_stats,
    increment_quest_quiz_count,
    increment_user_score,
    reset_user_streak,
    use_streak_freeze,
)
from utils.codingquestions import (
    get_available_categories,
    get_random_question,
    get_random_question_by_category,
)


class _PracticeSession(TypedDict):
    created_at: float
    correct: str
    interaction: discord.Interaction


class CodeBuddyQuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot, question_channel_id: int):
        self.bot = bot
        self.channel_id = question_channel_id

        self.current_question: str | None = None
        self.current_answer: str | None = None
        self.current_question_data: dict | None = None
        self.current_message: discord.Message | None = None
        self.question_active = False
        self.ignored_users = set()
        self.bonus_active = False

        self.frequency_minutes = 25

        # Practice question sessions ("knowledge mode") for /question.
        # Keyed by (user_id, channel_id) and validated on the user's next a/b/c message.
        self._practice_sessions: dict[tuple[int, int], _PracticeSession] = {}
        self._practice_timeout_seconds = 120

    def _cleanup_practice_sessions(self) -> None:
        now = time.monotonic()
        expired_keys = [
            key
            for key, data in self._practice_sessions.items()
            if now - data.get("created_at", 0.0) > self._practice_timeout_seconds
        ]
        for key in expired_keys:
            self._practice_sessions.pop(key, None)

    async def cog_load(self):
        self.post_question_loop.change_interval(minutes=self.frequency_minutes)
        self.post_question_loop.start()

    async def cog_unload(self):
        self.post_question_loop.cancel()

    def _build_question_embed(
        self, q: dict, title: str = "Coding Quiz"
    ) -> discord.Embed:
        options_letters = ["a", "b", "c"]
        options_text = "\n".join(
            f"**{letter})** {option}"
            for letter, option in zip(options_letters, q["options"], strict=True)
        )

        embed = discord.Embed(
            title=title,
            description=f"**{q['question']}**\n\n{options_text}",
            color=discord.Color.blurple(),
        )
        return embed

    @tasks.loop(minutes=25)
    async def post_question_loop(self):
        try:
            if self.question_active and self.current_message:
                try:
                    await self.current_message.delete()
                except discord.NotFound:
                    pass
                except Exception as e:
                    print(f"[Error deleting old message]: {e}")
                self._reset_question_state()

            channel = self.bot.get_channel(self.channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                print(
                    f"[Error] Channel ID {self.channel_id} not found or not messageable."
                )
                return

            channel = cast(discord.abc.Messageable, channel)

            try:
                q = get_random_question()
                self.current_question = q["question"]
                self.current_answer = q["correct"]
                self.current_question_data = q
                self.question_active = True
                self.ignored_users.clear()
                self.bonus_active = random.random() < 0.1
            except Exception as e:
                print(f"[Error fetching question]: {e}")
                return

            embed = self._build_question_embed(q)
            footer_text = (
                "BONUS QUESTION – double points!"
                if self.bonus_active
                else "Answer with 'a', 'b', or 'c'."
            )
            lang_name = q.get("language", "General")
            embed.set_footer(text=f"{lang_name} • {footer_text}")

            try:
                self.current_message = await channel.send(embed=embed)
            except Exception as e:
                print(f"[Error sending question message]: {e}")

        except Exception as e:
            print(f"[Unexpected error in post_question_loop]: {e}")

    def _reset_question_state(self):
        self.question_active = False
        self.current_question = None
        self.current_answer = None
        self.current_question_data = None
        self.current_message = None
        self.ignored_users.clear()
        self.bonus_active = False

    @post_question_loop.before_loop
    async def before_post_question(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot:
                return

            # 1) Main scheduled quiz answer checking (points/streaks) in the quiz channel.
            if self.question_active and message.channel.id == self.channel_id:
                user_id = message.author.id
                content = message.content.lower().strip()

                if content not in ["a", "b", "c"]:
                    return

                if user_id in self.ignored_users:
                    return

                if content == self.current_answer:
                    try:
                        await message.add_reaction("✅")
                    except Exception:
                        pass

                    points = 2 if self.bonus_active else 1
                    extra_bonus = 0

                    try:
                        await increment_user_score(user_id, points)
                    except Exception as e:
                        print(f"[Error incrementing user score]: {e}")

                    try:
                        quest_completed = await increment_quest_quiz_count(user_id)
                        if quest_completed:
                            try:
                                quest_embed = discord.Embed(
                                    title="Quest Completed!",
                                    description=(
                                        f"{message.author.mention} You completed the **Quiz** quest!\n\n"
                                        "**Rewards Earned:**\n"
                                        "• **0.2** Streak Freeze\n"
                                        "• **0.5** Save\n\n"
                                        "Use `?inventory` to check your items!"
                                    ),
                                    color=0x000000,
                                )
                                await message.channel.send(embed=quest_embed)
                            except Exception as e:
                                print(f"[Error sending quest completion message]: {e}")
                    except Exception as e:
                        print(f"[Error updating quest progress]: {e}")

                    try:
                        lb = await get_leaderboard(100)
                    except Exception as e:
                        print(f"[Error fetching leaderboard]: {e}")
                        lb = []

                    streak = 0
                    for uid, _score, s, _best in lb:
                        if uid == user_id:
                            streak = s
                            try:
                                if streak == 3:
                                    extra_bonus = 1
                                    await increment_user_score(user_id, extra_bonus)
                                elif streak == 5:
                                    extra_bonus = 2
                                    await increment_user_score(user_id, extra_bonus)
                            except Exception as e:
                                print(f"[Error applying streak bonus]: {e}")
                            break

                    total_points = points + extra_bonus
                    title = f"{streak}x Streak!"
                    embed = discord.Embed(
                        title=title,
                        description=f"{message.author.mention} answered correctly and earned **{total_points} point(s)**!",
                        color=discord.Color.green(),
                    )
                    if extra_bonus > 0:
                        embed.add_field(
                            name="Streak Bonus", value=f"+{extra_bonus}", inline=True
                        )
                    if self.bonus_active:
                        embed.set_footer(text="Bonus Question!")
                    try:
                        await message.channel.send(embed=embed)
                    except Exception as e:
                        print(f"[Error sending success embed]: {e}")

                    self._reset_question_state()
                else:
                    self.ignored_users.add(user_id)

                    try:
                        await message.add_reaction("❌")
                    except Exception:
                        pass

                    # ── Reveal the correct answer in the channel ───────────
                    if self.current_question_data is not None:
                        try:
                            correct_idx = ord(self.current_answer) - ord("a")
                            options = self.current_question_data.get("options", [])
                            if 0 <= correct_idx < len(options):
                                correct_text = options[correct_idx]
                                await message.channel.send(
                                    f"❌ {message.author.mention} The correct answer was **{self.current_answer}**: {correct_text}",
                                    delete_after=3,
                                )
                        except Exception as e:
                            print(f"[Error revealing correct answer]: {e}")

                    freeze_used = False
                    try:
                        freeze_used = await use_streak_freeze(user_id)
                    except Exception as e:
                        print(f"[Error checking streak freeze]: {e}")

                    if freeze_used:
                        try:
                            freeze_embed = discord.Embed(
                                title="Streak Freeze Activated!",
                                description=(
                                    f"{message.author.mention} Wrong answer, but your **Streak Freeze** protected your streak!\n\n"
                                    "Your streak remains intact."
                                ),
                                color=0x000000,
                            )
                            freeze_embed.set_footer(
                                text="Earn more freezes by completing daily quests!"
                            )
                            await message.channel.send(embed=freeze_embed)
                        except Exception as e:
                            print(f"[Error sending freeze message]: {e}")
                    else:
                        try:
                            await reset_user_streak(user_id)
                        except Exception as e:
                            print(f"[Error resetting user streak]: {e}")

                        try:
                            await message.channel.send(
                                f"{message.author.mention} Wrong answer! Streak reset to 0."
                            )
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            print(f"[Error sending wrong answer message]: {e}")

                return

            # 2) Practice question answer checking (no points) in any channel.
            self._cleanup_practice_sessions()
            content = message.content.lower().strip()
            if content not in ["a", "b", "c"]:
                return

            session_key = (message.author.id, message.channel.id)
            session = self._practice_sessions.get(session_key)
            if not session:
                return

            created_at = session.get("created_at", 0.0)
            if time.monotonic() - created_at > self._practice_timeout_seconds:
                self._practice_sessions.pop(session_key, None)
                return

            correct = session.get("correct", "").lower().strip()
            practice_interaction = session.get("interaction")
            try:
                if content == correct:
                    await message.add_reaction("✅")
                    # Reveal as ephemeral via the stored interaction
                    if practice_interaction and not practice_interaction.is_expired():
                        try:
                            await practice_interaction.followup.send(
                                f"{message.author.mention} Correct! ✅",
                                ephemeral=True,
                            )
                        except Exception:
                            await message.channel.send(
                                f"{message.author.mention} Correct! ✅",
                                allowed_mentions=discord.AllowedMentions(users=True),
                                delete_after=10,
                            )
                    else:
                        await message.channel.send(
                            f"{message.author.mention} Correct! ✅",
                            allowed_mentions=discord.AllowedMentions(users=True),
                            delete_after=10,
                        )
                else:
                    await message.add_reaction("❌")
                    # Reveal the correct answer as ephemeral via the stored interaction
                    if practice_interaction and not practice_interaction.is_expired():
                        try:
                            await practice_interaction.followup.send(
                                f"❌ Wrong. The correct answer is **{correct}**.",
                                ephemeral=True,
                            )
                        except Exception:
                            await message.channel.send(
                                f"{message.author.mention} Wrong. Correct answer is **{correct}**.",
                                allowed_mentions=discord.AllowedMentions(users=True),
                                delete_after=3,
                            )
                    else:
                        await message.channel.send(
                            f"{message.author.mention} Wrong. Correct answer is **{correct}**.",
                            allowed_mentions=discord.AllowedMentions(users=True),
                            delete_after=3,
                        )
            except Exception:
                pass
            finally:
                # One attempt per practice question.
                self._practice_sessions.pop(session_key, None)

        except Exception as e:
            print(f"[Unexpected error in on_message]: {e}")

    @app_commands.command(
        name="question",
        description="Get one practice question by category/language (no points).",
    )
    @app_commands.describe(
        category="Choose category like python, java, javascript, general, system design, etc.",
    )
    async def question(self, interaction: discord.Interaction, category: str):
        try:
            q = get_random_question_by_category(category)
            if not q:
                available = ", ".join(get_available_categories())
                await interaction.response.send_message(
                    f"Invalid category: `{category}`.\nAvailable: {available}",
                    ephemeral=True,
                )
                return

            embed = self._build_question_embed(q, title="Practice Question")
            embed.set_footer(
                text=f"{q.get('language', 'General')} • Knowledge mode (no points)"
            )
            await interaction.response.send_message(embed=embed)

            # Store correct answer for this user's next a/b/c message in this channel.
            # (Practice questions are not tied to the scheduled quiz channel.)
            try:
                msg = await interaction.original_response()
                channel_id = msg.channel.id
            except Exception:
                channel_id = interaction.channel_id

            if channel_id is not None:
                self._practice_sessions[(interaction.user.id, int(channel_id))] = {
                    "created_at": time.monotonic(),
                    "correct": str(q.get("correct", "")).lower().strip(),
                    "interaction": interaction,
                }

        except Exception as e:
            print(f"[Unexpected error in /question]: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Could not fetch a practice question right now.",
                    ephemeral=True,
                )

    @app_commands.command(
        name="frequency",
        description="Set CodeBuddy quiz frequency in minutes (1 to 30).",
    )
    @app_commands.describe(
        minutes="How often quiz questions appear in the quiz channel."
    )
    async def frequency(self, interaction: discord.Interaction, minutes: int):
        try:
            if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "You need `Manage Server` permission to change quiz frequency.",
                    ephemeral=True,
                )
                return

            if minutes < 1 or minutes > 30:
                await interaction.response.send_message(
                    "Frequency must be between **1** and **30** minutes.",
                    ephemeral=True,
                )
                return

            self.frequency_minutes = minutes
            self.post_question_loop.change_interval(minutes=minutes)

            await interaction.response.send_message(
                f"CodeBuddy quiz frequency updated to **{minutes} minute(s)**.",
                ephemeral=True,
            )
        except Exception as e:
            print(f"[Unexpected error in /frequency]: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Could not update quiz frequency.",
                    ephemeral=True,
                )

    @app_commands.command(
        name="codeleaderboard",
        description="Show the top players with the most correct answers.",
    )
    async def leaderboard(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="Code Leaderboard",
                description="Loading leaderboard...",
                color=discord.Color.gold(),
            )
            await interaction.response.send_message(embed=embed)

            lb = await get_leaderboard()
            if not lb:
                updated_embed = discord.Embed(
                    title="Code Leaderboard",
                    description="No leaderboard data yet.",
                    color=discord.Color.gold(),
                )
                try:
                    await interaction.edit_original_response(embed=updated_embed)
                except Exception:
                    pass
                return

            desc = ""
            medals = ["1.", "2.", "3."]
            for i, (user_id, score, streak, best) in enumerate(lb, 1):
                user = (
                    interaction.guild.get_member(user_id) if interaction.guild else None
                )
                if not user:
                    user = self.bot.get_user(user_id)
                mention = user.mention if user else f"<@{user_id}>"
                medal = medals[i - 1] if i <= len(medals) else f"{i}."
                desc += (
                    f"{medal} {mention} - {score} pts Streak: {streak} (Best: {best})\n"
                )

            final_embed = discord.Embed(
                title="Code Leaderboard",
                description=desc,
                color=discord.Color.gold(),
            )

            try:
                await interaction.edit_original_response(embed=final_embed)
            except Exception:
                pass

        except Exception as e:
            print(f"[Unexpected error in leaderboard command]: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Error fetching leaderboard.", ephemeral=True
                    )
                else:
                    await interaction.edit_original_response(
                        content="Error fetching leaderboard."
                    )
            except Exception:
                pass

    @commands.command(name="codeleaderboard", aliases=["clb"])
    async def codeleaderboard_prefix(self, ctx: commands.Context):
        """Show the top players with the most correct answers."""
        try:
            embed = discord.Embed(
                title="Code Leaderboard",
                description="Loading leaderboard...",
                color=discord.Color.gold(),
            )
            msg = await ctx.send(embed=embed)

            lb = await get_leaderboard()
            if not lb:
                updated_embed = discord.Embed(
                    title="Code Leaderboard",
                    description="No leaderboard data yet.",
                    color=discord.Color.gold(),
                )
                await msg.edit(embed=updated_embed)
                return

            desc = ""
            medals = ["1.", "2.", "3."]
            for i, (user_id, score, streak, best) in enumerate(lb, 1):
                user = ctx.guild.get_member(user_id) if ctx.guild else None
                if not user:
                    user = self.bot.get_user(user_id)
                mention = user.mention if user else f"<@{user_id}>"

                medal = medals[i - 1] if i <= len(medals) else f"{i}."
                desc += (
                    f"{medal} {mention} - {score} pts Streak: {streak} (Best: {best})\n"
                )

            final_embed = discord.Embed(
                title="Code Leaderboard",
                description=desc,
                color=discord.Color.gold(),
            )

            await msg.edit(embed=final_embed)

        except Exception as e:
            print(f"[Unexpected error in codeleaderboard command]: {e}")
            await ctx.send("Error fetching leaderboard.")

    @app_commands.command(
        name="codestats", description="Show your personal coding quiz stats."
    )
    async def codestats(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            try:
                score, streak, best = await get_user_stats(user_id)
                rank = await get_user_rank(user_id)
                gap, higher_id = await get_score_gap(user_id)
            except Exception as e:
                print(f"[Error fetching user stats]: {e}")
                await interaction.response.send_message(
                    "Error fetching your stats.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Stats",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Points", value=str(score), inline=False)
            embed.add_field(
                name="Streak", value=f"{streak} (current)\n{best} (best)", inline=False
            )
            embed.add_field(
                name="Rank", value=f"#{rank}" if rank else "Unranked", inline=False
            )

            if gap is not None and higher_id is not None:
                try:
                    higher_user = self.bot.get_user(
                        higher_id
                    ) or await self.bot.fetch_user(higher_id)
                    higher_name = (
                        higher_user.display_name if higher_user else f"User {higher_id}"
                    )
                except Exception:
                    higher_name = f"User {higher_id}"
                embed.set_footer(text=f"{gap} point(s) behind {higher_name}")
            else:
                embed.set_footer(text="You are at the top!")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"[Unexpected error in codestats command]: {e}")
            try:
                await interaction.response.send_message(
                    "Error displaying your stats.", ephemeral=True
                )
            except Exception:
                pass

    @commands.command(name="codestats", aliases=["cst"])
    async def codestats_prefix(self, ctx: commands.Context):
        """Show your personal coding quiz stats."""
        try:
            user_id = ctx.author.id
            try:
                score, streak, best = await get_user_stats(user_id)
                rank = await get_user_rank(user_id)
                gap, higher_id = await get_score_gap(user_id)
            except Exception as e:
                print(f"[Error fetching user stats]: {e}")
                await ctx.send("Error fetching your stats.")
                return

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Stats",
                color=discord.Color.blurple(),
            )
            embed.add_field(name="Points", value=str(score), inline=False)
            embed.add_field(
                name="Streak", value=f"{streak} (current)\n{best} (best)", inline=False
            )
            embed.add_field(
                name="Rank", value=f"#{rank}" if rank else "Unranked", inline=False
            )

            if gap is not None and higher_id is not None:
                try:
                    higher_user = self.bot.get_user(
                        higher_id
                    ) or await self.bot.fetch_user(higher_id)
                    higher_name = (
                        higher_user.display_name if higher_user else f"User {higher_id}"
                    )
                except Exception:
                    higher_name = f"User {higher_id}"
                embed.set_footer(text=f"{gap} point(s) behind {higher_name}")
            else:
                embed.set_footer(text="You are at the top!")

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"[Unexpected error in codestats command]: {e}")
            await ctx.send("Error displaying your stats.")


async def setup(bot: commands.Bot):
    question_channel_id = int(os.getenv("QUESTION_CHANNEL_ID", "0"))
    if question_channel_id == 0:
        print("[Warning] QUESTION_CHANNEL_ID not set. QuizCog will not work correctly.")
    try:
        await bot.add_cog(CodeBuddyQuizCog(bot, question_channel_id))
    except Exception as e:
        print(f"[Error setting up QuizCog]: {e}")
