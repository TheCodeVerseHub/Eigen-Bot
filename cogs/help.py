import discord
from discord.ext import commands
from discord import app_commands
from collections.abc import Iterable, Iterator
from typing import Optional, Union, cast


# Emoji mapping for each cog category
COG_EMOJIS = {
    "admin": "",
    "fun": "",
    "tags": "",
    "communitycommands": "",
    "election": "",
    "misc": "",
    "starboardsystem": "",
    "utilityextra": "",
    "invitetracker": "",
    "afksystem": "",
    "tickets": "",
    "codebuddyleaderboardcog": "",
    "codebuddyquizcog": "",
    "codebuddyhelpcog": "",
    "dailyquestscog": "📋",
    "suggestions": "",
    "bumpleaderboard": "",
}

# Category descriptions
COG_DESCRIPTIONS = {
    "admin": "Administrator commands for managing the bot",
    "fun": "Entertainment commands including jokes, trivia, and games",
    "tags": "Create and manage custom text snippets for your server",
    "communitycommands": "Engage your community with quotes and memes",
    "election": "Democratic voting system with weighted votes",
    "misc": "Support commands, timestamps, admin utilities (/say, /edit, /react), and more",
    "starboardsystem": "Highlight the best messages with stars",
    "utilityextra": "Extra utility commands like reminders, dice, and emotes",
    "afksystem": "Away From Keyboard system - Set AFK status with custom reasons, auto-respond to mentions, and track time away",
    "birthday": "Birthday tracking and celebration system",
    "tickets": "Support ticket system - Create and manage support tickets for your server",
    "codebuddyleaderboardcog": "View coding leaderboards, weekly stats, and streaks",
    "codebuddyquizcog": "Test your coding knowledge with quizzes",
    "codebuddyhelpcog": "Help and information for CodeBuddy features",
    "dailyquestscog": "Complete daily quests to earn partial streak freezes and saves (quiz + counting tasks)",
    "counting": "Counting game with warnings, highscores, and save protection",
    "staffapplications": "Staff application panel, review buttons, and admin config",
    "suggestions": "Submit suggestions with voting reactions + discussion threads",
    "bumpleaderboard": "Track Disboard /bump activity with leaderboards and stats",
    "chowkidar": "Watchlist / tracking: track a user and log their actions (staff only)",
}


AppCommand = Union[app_commands.Command, app_commands.Group, app_commands.ContextMenu]


def _flatten_app_commands(cmds: Iterable[AppCommand]) -> Iterator[AppCommand]:
    """Yield app commands recursively (includes group subcommands)."""
    for cmd in cmds:
        yield cmd
        if isinstance(cmd, app_commands.Group):
            yield from _flatten_app_commands(cmd.commands)


def _slash_commands_for_cog(bot: commands.Bot, cog: commands.Cog) -> list[AppCommand]:
    """Return slash commands bound to the given cog (includes group subcommands)."""
    bound: list[AppCommand] = []
    for cmd in _flatten_app_commands(list(bot.tree.get_commands())):
        if getattr(cmd, "binding", None) is cog:
            bound.append(cmd)
    return bound


class HelpSelect(discord.ui.Select):
    """Dropdown menu for selecting help categories."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Build options from loaded cogs
        options = [
            discord.SelectOption(
                label="Home",
                value="home",
                description="Return to main help menu"
            )
        ]
        
        quiz_command_count = 0
        
        # Cogs to merge into Misc (kept lightweight)
        merged_into_misc = ['birthday', 'election', 'starboardsystem', 'tags']
        
        # Add options for each loaded cog (use actual cog names from bot.cogs)
        for cog_name, cog in sorted(bot.cogs.items()):
            # Skip help cog itself
            if cog_name.lower() == 'helpcog':
                continue
            
            # Check if this is a CodeBuddy cog
            if cog_name.lower().startswith('codebuddy'):
                # Count commands for the unified Quiz category
                visible_count = sum(1 for cmd in cog.get_commands() 
                                  if not getattr(cmd, 'hidden', False) and cmd.enabled)
                quiz_command_count += visible_count
                continue  # Skip adding individual CodeBuddy cogs
            
            # Skip cogs that are merged into Misc
            if cog_name.lower() in merged_into_misc:
                continue
            
            # Get visible commands count
            visible_prefix = [
                cmd for cmd in cog.get_commands()
                if not getattr(cmd, 'hidden', False) and cmd.enabled
            ]
            prefix_names = {cmd.name for cmd in visible_prefix}
            slash_cmds = _slash_commands_for_cog(bot, cog)
            visible_slash_only = [c for c in slash_cmds if c.name not in prefix_names]
            visible_count = len(visible_prefix) + len(visible_slash_only)
            
            if visible_count == 0:
                continue
                
            description = COG_DESCRIPTIONS.get(cog_name.lower(), "View commands in this category")
            
            options.append(
                discord.SelectOption(
                    label=f"{cog_name}",
                    value=cog_name.lower(),
                    description=f"{description[:50]}"
                )
            )
        
        # Add unified Quiz category if there are CodeBuddy commands
        if quiz_command_count > 0:
            options.insert(1, discord.SelectOption(
                label="Quiz",
                value="quiz",
                description="Coding quizzes, leaderboards, and stats"
            ))
        
        super().__init__(
            placeholder="Select a category to view commands...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection."""
        selected = self.values[0]
        
        if selected == "home":
            embed = self._create_home_embed()
        else:
            embed = self._create_category_embed(selected)
        
        await interaction.response.edit_message(embed=embed, view=self.view)
    
    def _create_home_embed(self) -> discord.Embed:
        """Create the main help embed."""
        embed = discord.Embed(
            title="Eigen Bot · Help",
            description=(
                "Feature-rich Discord bot for community engagement, support, and utilities.\n\n"
                "**Commands:**\n"
                "Prefix: `?command` (e.g. `?helpmenu`)\n"
                "Slash: `/command` (e.g. `/help`)\n\n"
                "**Support:** [discord.gg/4TkQYz7qea](https://discord.gg/4TkQYz7qea) \n\n"
                "*Select a category below to view commands*"
            ),
            color=0x000000
        )
        
        # Add category overview (use actual loaded cogs)
        categories = []
        quiz_count = 0
        merged_into_misc = ['birthday', 'election', 'starboardsystem', 'tags']
        misc_count = 0
        
        for cog_name, cog in sorted(self.bot.cogs.items()):
            # Skip help cog
            if cog_name.lower() == 'helpcog':
                continue
            
            # Count CodeBuddy commands separately
            if cog_name.lower().startswith('codebuddy'):
                visible_count = sum(1 for cmd in cog.get_commands() 
                                  if not getattr(cmd, 'hidden', False) and cmd.enabled)
                quiz_count += visible_count
                continue
            
            # Count commands from cogs merged into Misc
            if cog_name.lower() in merged_into_misc or cog_name.lower() == 'misc':
                visible_prefix = [
                    cmd for cmd in cog.get_commands()
                    if not getattr(cmd, 'hidden', False) and cmd.enabled
                ]
                prefix_names = {cmd.name for cmd in visible_prefix}
                slash_cmds = _slash_commands_for_cog(self.bot, cog)
                visible_slash_only = [c for c in slash_cmds if c.name not in prefix_names]
                misc_count += (len(visible_prefix) + len(visible_slash_only))
                continue
            
            visible_prefix = [
                cmd for cmd in cog.get_commands()
                if not getattr(cmd, 'hidden', False) and cmd.enabled
            ]
            prefix_names = {cmd.name for cmd in visible_prefix}
            slash_cmds = _slash_commands_for_cog(self.bot, cog)
            visible_slash_only = [c for c in slash_cmds if c.name not in prefix_names]
            visible_count = len(visible_prefix) + len(visible_slash_only)
            
            if visible_count > 0:
                categories.append(f"**{cog_name}** · {visible_count} commands")
        
        # Add Quiz category if there are CodeBuddy commands
        if quiz_count > 0:
            categories.insert(0, f"**Quiz** · {quiz_count} commands")
        
        # Add Misc category with merged commands
        if misc_count > 0:
            categories.insert(0 if quiz_count == 0 else 1, f"**Misc** · {misc_count} commands")
        
        if categories:
            embed.add_field(
                name="Available Categories",
                value="\n".join("- "+cat for cat in categories),
                inline=False
            )
        
        embed.set_footer(text="Use ?helpmenu <command> for detailed command help")
        return embed
    
    def _create_category_embed(self, cog_name: str) -> discord.Embed:
        """Create embed for a specific category."""
        
        # Handle special Quiz category that combines all CodeBuddy cogs
        if cog_name.lower() == 'quiz':
            embed = discord.Embed(
                title="Quiz Commands",
                description="Coding quizzes, leaderboards, and personal statistics",
                color=0x000000
            )
            
            # Collect all commands from CodeBuddy cogs
            commands_list = []
            for name, cog in self.bot.cogs.items():
                if name.lower().startswith('codebuddy'):
                    for cmd in cog.get_commands():
                        if not getattr(cmd, 'hidden', False) and cmd.enabled:
                            signature = f"{cmd.name} {cmd.signature}".strip()
                            desc = cmd.short_doc or "No description"
                            if len(desc) > 80:
                                desc = desc[:77] + "..."
                            commands_list.append(f"`{signature}`\n*{desc}*")
            
            if commands_list:
                # Split into chunks by character count (max 1000 to be safe)
                current_chunk = []
                current_length = 0
                field_number = 0
                
                for cmd_text in commands_list:
                    cmd_length = len(cmd_text) + 2  # +2 for "\n\n" separator
                    
                    # If adding this command would exceed limit, start new field
                    if current_length + cmd_length > 1000 and current_chunk:
                        field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                        embed.add_field(
                            name=field_name,
                            value="\n\n".join(current_chunk),
                            inline=False
                        )
                        current_chunk = []
                        current_length = 0
                        field_number += 1
                    
                    current_chunk.append(cmd_text)
                    current_length += cmd_length
                
                # Add remaining commands
                if current_chunk:
                    field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                    embed.add_field(
                        name=field_name,
                        value="\n\n".join(current_chunk),
                        inline=False
                    )
            else:
                embed.description = "No commands available in this category."
            
            embed.set_footer(text="Use ?helpmenu <command> for detailed help")
            return embed
        
        # Handle special Misc category that combines multiple cogs
        if cog_name.lower() == 'misc':
            merged_cogs = ['misc', 'birthday', 'election', 'starboardsystem', 'tags']
            
            embed = discord.Embed(
                title="Misc Commands",
                description="Support, feedback, birthdays, elections, starboard, tags, and more",
                color=0x000000
            )
            
            # Collect all commands from merged cogs
            commands_list = []
            for name, cog in self.bot.cogs.items():
                if name.lower() in merged_cogs:
                    visible_prefix = [
                        cmd for cmd in cog.get_commands()
                        if not getattr(cmd, 'hidden', False) and cmd.enabled
                    ]
                    prefix_names = {cmd.name for cmd in visible_prefix}

                    for cmd in visible_prefix:
                        signature = f"{cmd.name} {cmd.signature}".strip()
                        desc = cmd.short_doc or "No description"
                        if len(desc) > 80:
                            desc = desc[:77] + "..."
                        commands_list.append(f"`{signature}`\n*{desc}*")

                    for sc in _slash_commands_for_cog(self.bot, cog):
                        if sc.name in prefix_names:
                            continue
                        desc = getattr(sc, "description", None) or "No description"
                        if len(desc) > 80:
                            desc = desc[:77] + "..."
                        commands_list.append(f"`/{sc.name}`\n*{desc}*")
            
            if commands_list:
                # Split into chunks by character count (max 1000 to be safe)
                current_chunk = []
                current_length = 0
                field_number = 0
                
                for cmd_text in commands_list:
                    cmd_length = len(cmd_text) + 2  # +2 for "\n\n" separator
                    
                    # If adding this command would exceed limit, start new field
                    if current_length + cmd_length > 1000 and current_chunk:
                        field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                        embed.add_field(
                            name=field_name,
                            value="\n\n".join(current_chunk),
                            inline=False
                        )
                        current_chunk = []
                        current_length = 0
                        field_number += 1
                    
                    current_chunk.append(cmd_text)
                    current_length += cmd_length
                
                # Add remaining commands
                if current_chunk:
                    field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                    embed.add_field(
                        name=field_name,
                        value="\n\n".join(current_chunk),
                        inline=False
                    )
            else:
                embed.description = "No commands available in this category."
            
            embed.set_footer(text="Use ?helpmenu <command> for detailed help")
            return embed
        
        # Find the cog (case-insensitive)
        cog = None
        actual_cog_name = None
        for name, c in self.bot.cogs.items():
            if name.lower() == cog_name.lower():
                cog = c
                actual_cog_name = name
                break
        
        if cog is None:
            return discord.Embed(
                title="Category Not Found",
                description=f"The category `{cog_name}` could not be found.",
                color=0x000000
            )
        
        description = COG_DESCRIPTIONS.get(cog_name.lower(), "Commands in this category")
        
        embed = discord.Embed(
            title=f"{actual_cog_name} Commands",
            description=description,
            color=0x000000
        )
        
        # Group commands by type or just list them
        commands_list = []
        visible_prefix = [
            cmd for cmd in cog.get_commands()
            if not getattr(cmd, 'hidden', False) and cmd.enabled
        ]
        prefix_names = {cmd.name for cmd in visible_prefix}

        for cmd in visible_prefix:
            # Format: command name + signature + description
            signature = f"{cmd.name} {cmd.signature}".strip()
            desc = cmd.short_doc or "No description"
            # Limit description length to prevent overflow
            if len(desc) > 80:
                desc = desc[:77] + "..."
            commands_list.append(f"`{signature}`\n*{desc}*")

        for sc in _slash_commands_for_cog(self.bot, cog):
            if sc.name in prefix_names:
                continue
            desc = getattr(sc, "description", None) or "No description"
            if len(desc) > 80:
                desc = desc[:77] + "..."
            commands_list.append(f"`/{sc.name}`\n*{desc}*")
        
        if commands_list:
            # Split into chunks by character count (max 1000 to be safe)
            current_chunk = []
            current_length = 0
            field_number = 0
            
            for cmd_text in commands_list:
                cmd_length = len(cmd_text) + 2  # +2 for "\n\n" separator
                
                # If adding this command would exceed limit, start new field
                if current_length + cmd_length > 1000 and current_chunk:
                    field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                    embed.add_field(
                        name=field_name,
                        value="\n\n".join(current_chunk),
                        inline=False
                    )
                    current_chunk = []
                    current_length = 0
                    field_number += 1
                
                current_chunk.append(cmd_text)
                current_length += cmd_length
            
            # Add remaining commands
            if current_chunk:
                field_name = "Commands" if field_number == 0 else f"Commands (continued {field_number})"
                embed.add_field(
                    name=field_name,
                    value="\n\n".join(current_chunk),
                    inline=False
                )
        else:
            embed.description = "No commands available in this category."
        
        embed.set_footer(text="Use ?helpmenu <command> for detailed help")
        return embed


class HelpView(discord.ui.View):
    """View containing the help dropdown menu."""
    
    def __init__(self, bot: commands.Bot, author_id: int):
        super().__init__(timeout=180)  # 3 minute timeout
        self.bot = bot
        self.author_id = author_id
        self.add_item(HelpSelect(bot))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to use the dropdown."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This help menu is not for you. Use `?helpmenu` to get your own.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        """Disable the dropdown after timeout."""
        # Disable all items in the view
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True


class HelpCog(commands.Cog):
    """Interactive help command with dropdown menus.

    Provides a modern, user-friendly help interface with dropdown menus to browse categories.
    Works as a hybrid command so both prefix (`?helpmenu`) and slash (`/help`) are available.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="helpmenu", description="Show help for commands or a specific command/cog")
    async def helpmenu(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Show interactive help menu or detailed help for a specific command/category."""
        await self._show_help(ctx, query)
    
    @app_commands.command(name="help", description="Show help for commands or a specific command/cog")
    @app_commands.describe(query="Optional command or cog name to show detailed help for")
    async def help_slash(self, interaction: discord.Interaction, query: Optional[str] = None):
        """Show interactive help menu or detailed help for a specific command/category (slash version)."""
        # If a specific command or cog name was provided, show detailed help
        if query:
            await self._detailed_help_slash(interaction, query)
            return

        # Create the view with dropdown
        view = HelpView(self.bot, interaction.user.id)
        
        # Get the home embed from the select menu
        select = cast(HelpSelect, view.children[0])
        embed = select._create_home_embed()
        
        # Send with the view
        await interaction.response.send_message(embed=embed, view=view)
    
    async def _show_help(self, ctx: commands.Context, query: Optional[str] = None):
        """Internal method to show help menu."""
        
        # If a specific command or cog name was provided, show detailed help
        if query:
            await self._detailed_help(ctx, query)
            return

        # Create view with dropdown and get the embed from it
        view = HelpView(self.bot, ctx.author.id)
        select = cast(HelpSelect, view.children[0])
        embed = select._create_home_embed()
        
        await ctx.send(embed=embed, view=view)

    async def _detailed_help(self, ctx: commands.Context, query: str):
        """Show detailed help for a specific command or category."""
        # Try to find a command first
        cmd = self.bot.get_command(query)
        if cmd:
            embed = discord.Embed(
                title=f" Command: {cmd.qualified_name}",
                color=discord.Color.blue()
            )
            
            # Add usage
            usage = f"?{cmd.qualified_name} {cmd.signature}".strip()
            embed.add_field(
                name="Usage",
                value=f"```\n{usage}\n```",
                inline=False
            )
            
            # Add description
            description = cmd.help or cmd.short_doc or "No description available."
            embed.add_field(
                name="Description",
                value=description,
                inline=False
            )
            
            # Add aliases if any
            if hasattr(cmd, 'aliases') and cmd.aliases:
                embed.add_field(
                    name="Aliases",
                    value=", ".join(f"`{alias}`" for alias in cmd.aliases),
                    inline=False
                )
            
            # Add cooldown if any
            if cmd._buckets and cmd._buckets._cooldown:
                cooldown = cmd._buckets._cooldown
                embed.add_field(
                    name="Cooldown",
                    value=f"{cooldown.rate} use(s) per {cooldown.per}s",
                    inline=True
                )
            
            embed.set_footer(text="Tip: Most commands work with both ? prefix and / slash commands!")
            await ctx.send(embed=embed)
            return

        # Try to find a slash command by name
        slash_cmd = None
        for sc in _flatten_app_commands(list(self.bot.tree.get_commands())):
            if sc.name.lower() == query.lower():
                slash_cmd = sc
                break

        if slash_cmd:
            embed = discord.Embed(
                title=f" Slash Command: /{slash_cmd.name}",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Usage",
                value=f"`/{slash_cmd.name}`",
                inline=False
            )

            description = getattr(slash_cmd, "description", None) or "No description available."
            embed.add_field(name="Description", value=description, inline=False)

            params = getattr(slash_cmd, "parameters", None)
            if params:
                param_lines = []
                for p in params:
                    pname = getattr(p, "name", "")
                    pdesc = getattr(p, "description", "") or ""
                    required = getattr(p, "required", False)
                    req = "required" if required else "optional"
                    line = f"{pname} ({req})"
                    if pdesc:
                        line += f" - {pdesc}"
                    param_lines.append(line)

                if param_lines:
                    embed.add_field(name="Parameters", value="\n".join(param_lines), inline=False)

            embed.set_footer(text="Tip: Most commands work with both ? prefix and / slash commands!")
            await ctx.send(embed=embed)
            return

        # Try to find a cog (case-insensitive)
        cog = None
        actual_cog_name = None
        for name, c in self.bot.cogs.items():
            if name.lower() == query.lower():
                cog = c
                actual_cog_name = name
                break
        
        if cog and actual_cog_name:
            emoji = COG_EMOJIS.get(actual_cog_name.lower(), "")
            description = COG_DESCRIPTIONS.get(actual_cog_name.lower(), "Commands in this category")
            
            embed = discord.Embed(
                title=f"{emoji} {actual_cog_name} Commands",
                description=description,
                color=discord.Color.green()
            )
            
            commands_list = []
            visible_prefix = [
                c for c in cog.get_commands()
                if not getattr(c, 'hidden', False) and c.enabled
            ]
            prefix_names = {c.name for c in visible_prefix}

            for c in visible_prefix:
                signature = f"{c.name} {c.signature}".strip()
                desc = c.short_doc or "No description"
                commands_list.append(f"`{signature}`\n└─ {desc}")

            for sc in _slash_commands_for_cog(self.bot, cog):
                if sc.name in prefix_names:
                    continue
                desc = getattr(sc, "description", None) or "No description"
                commands_list.append(f"`/{sc.name}`\n└─ {desc}")

            if commands_list:
                # Split into chunks if too long
                chunk_size = 10
                for i in range(0, len(commands_list), chunk_size):
                    chunk = commands_list[i:i+chunk_size]
                    field_name = "Commands" if i == 0 else "Commands (continued)"
                    embed.add_field(
                        name=field_name,
                        value="\n\n".join(chunk),
                        inline=False
                    )
            else:
                embed.description = "No visible commands in this category."

            embed.set_footer(text="Use ?helpmenu <command> for detailed command help")
            await ctx.send(embed=embed)
            return

        # If nothing found
        await ctx.send(
            embed=discord.Embed(
                title=" Not Found",
                description=f"No command or category named `{query}` was found.\n\nUse `?helpmenu` to see all available commands.",
                color=discord.Color.red()
            )
        )

    async def _detailed_help_slash(self, interaction: discord.Interaction, query: str):
        """Show detailed help for a specific command or category (slash version)."""
        # Try to find a command first
        cmd = self.bot.get_command(query)
        if cmd:
            embed = discord.Embed(
                title=f"Command: {cmd.qualified_name}",
                color=0x000000
            )
            
            # Add usage
            usage = f"?{cmd.qualified_name} {cmd.signature}".strip()
            embed.add_field(
                name="Usage",
                value=f"`{usage}`",
                inline=False
            )
            
            # Add description
            description = cmd.help or cmd.short_doc or "No description available."
            embed.add_field(
                name="Description",
                value=description,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            return

        # Try to find a slash command by name
        slash_cmd = None
        for sc in _flatten_app_commands(list(self.bot.tree.get_commands())):
            if sc.name.lower() == query.lower():
                slash_cmd = sc
                break

        if slash_cmd:
            embed = discord.Embed(
                title=f"Slash Command: /{slash_cmd.name}",
                color=0x000000
            )
            embed.add_field(name="Usage", value=f"`/{slash_cmd.name}`", inline=False)
            description = getattr(slash_cmd, "description", None) or "No description available."
            embed.add_field(name="Description", value=description, inline=False)

            params = getattr(slash_cmd, "parameters", None)
            if params:
                param_lines = []
                for p in params:
                    pname = getattr(p, "name", "")
                    pdesc = getattr(p, "description", "") or ""
                    required = getattr(p, "required", False)
                    req = "required" if required else "optional"
                    line = f"{pname} ({req})"
                    if pdesc:
                        line += f" - {pdesc}"
                    param_lines.append(line)
                if param_lines:
                    embed.add_field(name="Parameters", value="\n".join(param_lines), inline=False)

            await interaction.response.send_message(embed=embed)
            return

        # Try to find a cog (case-insensitive)
        cog = None
        actual_cog_name = None
        for name, c in self.bot.cogs.items():
            if name.lower() == query.lower():
                cog = c
                actual_cog_name = name
                break
        
        if cog and actual_cog_name:
            description = COG_DESCRIPTIONS.get(actual_cog_name.lower(), "Commands in this category")
            
            embed = discord.Embed(
                title=f"{actual_cog_name} Commands",
                description=description,
                color=0x000000
            )
            
            commands_list = []
            visible_prefix = [
                c for c in cog.get_commands()
                if not getattr(c, 'hidden', False) and c.enabled
            ]
            prefix_names = {c.name for c in visible_prefix}

            for c in visible_prefix:
                signature = f"{c.name} {c.signature}".strip()
                desc = c.short_doc or "No description"
                commands_list.append(f"`{signature}`\n*{desc}*")

            for sc in _slash_commands_for_cog(self.bot, cog):
                if sc.name in prefix_names:
                    continue
                desc = getattr(sc, "description", None) or "No description"
                commands_list.append(f"`/{sc.name}`\n*{desc}*")

            if commands_list:
                # Split into chunks if too long
                chunk_size = 10
                for i in range(0, len(commands_list), chunk_size):
                    chunk = commands_list[i:i+chunk_size]
                    field_name = "Commands" if i == 0 else "Commands (continued)"
                    embed.add_field(
                        name=field_name,
                        value="\n\n".join(chunk),
                        inline=False
                    )
            else:
                embed.description = "No visible commands in this category."

            await interaction.response.send_message(embed=embed)
            return

        # If nothing found
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Not Found",
                description=f"No command or category named `{query}` was found.\n\nUse `/help` to see all available commands.",
                color=0x000000
            )
        )


async def setup(bot: commands.Bot):
    # Aggressively remove any existing 'help' registration (prefix & app commands)
    try:
        # Remove prefix/legacy command if present
        if bot.get_command('help'):
            try:
                bot.remove_command('help')
            except Exception:
                # Best-effort removal
                pass

        # Remove any app command named 'help' from the command tree (guild/global)
        try:
            # Clear commands with the name 'help' on the tree (best-effort)
            for cmd in list(bot.tree.get_commands()):
                if getattr(cmd, 'name', '') == 'help':
                    try:
                        bot.tree.remove_command(cmd.name, guild=None)
                    except Exception:
                        # ignore failures removing individual commands
                        pass
        except Exception:
            pass
    except Exception:
        pass

    await bot.add_cog(HelpCog(bot))
