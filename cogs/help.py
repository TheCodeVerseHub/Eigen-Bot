import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


# Emoji mapping for each cog category
COG_EMOJIS = {
    "admin": "🔧",
    "economy": "💰",
    "fun": "🎭",
    "tags": "🏷️",
    "community": "👥",
    "election": "🗳️",
    "highlights": "🔔",
    "misc": "📝",
    "starboard": "⭐",
    "whois_alias": "🔍",
    "utility_extra": "🛠️",
}

# Category descriptions
COG_DESCRIPTIONS = {
    "admin": "Administrator commands for managing the bot and economy",
    "economy": "Virtual currency system with wallets, banks, and income commands",
    "fun": "Entertainment commands including jokes, trivia, and games",
    "tags": "Create and manage custom text snippets for your server",
    "community": "Engage your community with quotes, questions, and memes",
    "election": "Democratic voting system with weighted votes",
    "highlights": "Get notified when your keywords are mentioned",
    "misc": "Miscellaneous utility commands",
    "starboard": "Highlight the best messages with stars",
    "whois_alias": "User information and lookup commands",
    "utility_extra": "Extra utility commands like reminders, dice, and emotes",
}


class HelpSelect(discord.ui.Select):
    """Dropdown menu for selecting help categories."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Build options from loaded cogs
        options = [
            discord.SelectOption(
                label="🏠 Home",
                value="home",
                description="Return to main help menu",
                emoji="🏠"
            )
        ]
        
        # Add options for each loaded cog
        available = getattr(bot, 'available_cogs', list(bot.cogs.keys()))
        for cog_name in available:
            cog = bot.get_cog(cog_name)
            if cog is None or cog_name.lower() == 'help':
                continue
            
            # Get visible commands count
            visible_count = sum(1 for cmd in cog.get_commands() 
                              if not getattr(cmd, 'hidden', False) and cmd.enabled)
            
            if visible_count == 0:
                continue
                
            emoji = COG_EMOJIS.get(cog_name.lower(), "📁")
            description = COG_DESCRIPTIONS.get(cog_name.lower(), "View commands in this category")
            
            options.append(
                discord.SelectOption(
                    label=f"{cog_name.title()}",
                    value=cog_name.lower(),
                    description=f"{description[:50]}",
                    emoji=emoji
                )
            )
        
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
            title="📚 Eigen Bot - Help Menu",
            description=(
                "Welcome to Eigen Bot! A feature-rich Discord bot with economy, games, and community features.\n\n"
                "**How to use commands:**\n"
                "• Prefix: `f?command` (e.g., `f?balance`)\n"
                "• Slash: `/command` (e.g., `/balance`)\n\n"
                "**Select a category below to view commands!**"
            ),
            color=discord.Color.blue()
        )
        
        # Add category overview
        available = getattr(self.bot, 'available_cogs', list(self.bot.cogs.keys()))
        categories = []
        for cog_name in available:
            cog = self.bot.get_cog(cog_name)
            if cog is None or cog_name.lower() == 'help':
                continue
            
            visible_count = sum(1 for cmd in cog.get_commands() 
                              if not getattr(cmd, 'hidden', False) and cmd.enabled)
            
            if visible_count > 0:
                emoji = COG_EMOJIS.get(cog_name.lower(), "📁")
                categories.append(f"{emoji} **{cog_name.title()}** - {visible_count} commands")
        
        if categories:
            embed.add_field(
                name="📂 Available Categories",
                value="\n".join(categories),
                inline=False
            )
        
        embed.set_footer(text="Use f?help <command> for detailed command help • Tip: Try the dropdown menu!")
        return embed
    
    def _create_category_embed(self, cog_name: str) -> discord.Embed:
        """Create embed for a specific category."""
        cog = self.bot.get_cog(cog_name)
        if cog is None:
            return discord.Embed(
                title="❌ Category Not Found",
                description=f"The category `{cog_name}` could not be found.",
                color=discord.Color.red()
            )
        
        emoji = COG_EMOJIS.get(cog_name.lower(), "📁")
        description = COG_DESCRIPTIONS.get(cog_name.lower(), "Commands in this category")
        
        embed = discord.Embed(
            title=f"{emoji} {cog_name.title()} Commands",
            description=description,
            color=discord.Color.green()
        )
        
        # Group commands by type or just list them
        commands_list = []
        for cmd in cog.get_commands():
            if not getattr(cmd, 'hidden', False) and cmd.enabled:
                # Format: command name + signature + description
                signature = f"{cmd.name} {cmd.signature}".strip()
                desc = cmd.short_doc or "No description"
                commands_list.append(f"`{signature}`\n└─ {desc}")
        
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
            embed.description = "No commands available in this category."
        
        embed.set_footer(text=f"Use f?help <command> for detailed help • Select another category from the menu")
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
                "❌ This help menu is not for you! Use `f?help` to get your own.",
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
    Works as a hybrid command so both prefix (`f?help`) and slash (`/help`) are available.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show help for commands or a specific command/cog")
    @app_commands.describe(query="Optional command or cog name to show detailed help for")
    async def help(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Show interactive help menu or detailed help for a specific command/category."""
        
        # If a specific command or cog name was provided, show detailed help
        if query:
            await self._detailed_help(ctx, query)
            return

        # Create main help embed with dropdown menu
        embed = discord.Embed(
            title="📚 Eigen Bot - Help Menu",
            description=(
                "Welcome to Eigen Bot! A feature-rich Discord bot with economy, games, and community features.\n\n"
                "**How to use commands:**\n"
                "• Prefix: `f?command` (e.g., `f?balance`)\n"
                "• Slash: `/command` (e.g., `/balance`)\n\n"
                "**Select a category below to view commands!**"
            ),
            color=discord.Color.blue()
        )
        
        # Add category overview
        available = getattr(self.bot, 'available_cogs', list(self.bot.cogs.keys()))
        categories = []
        for cog_name in available:
            cog = self.bot.get_cog(cog_name)
            if cog is None or cog_name.lower() == 'help':
                continue
            
            visible_count = sum(1 for cmd in cog.get_commands() 
                              if not getattr(cmd, 'hidden', False) and cmd.enabled)
            
            if visible_count > 0:
                emoji = COG_EMOJIS.get(cog_name.lower(), "📁")
                categories.append(f"{emoji} **{cog_name.title()}** - {visible_count} commands")
        
        if categories:
            embed.add_field(
                name="📂 Available Categories",
                value="\n".join(categories),
                inline=False
            )
        
        embed.set_footer(text="Use f?help <command> for detailed command help • Tip: Try the dropdown menu!")
        
        # Create view with dropdown
        view = HelpView(self.bot, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    async def _detailed_help(self, ctx: commands.Context, query: str):
        """Show detailed help for a specific command or category."""
        # Try to find a command first
        cmd = self.bot.get_command(query)
        if cmd:
            embed = discord.Embed(
                title=f"📖 Command: {cmd.qualified_name}",
                color=discord.Color.blue()
            )
            
            # Add usage
            usage = f"f?{cmd.qualified_name} {cmd.signature}".strip()
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
            
            embed.set_footer(text="Tip: Most commands work with both f? prefix and / slash commands!")
            await ctx.send(embed=embed)
            return

        # Try to find a cog
        cog = self.bot.get_cog(query)
        if cog is None:
            # Try case-insensitive search
            for cog_name in self.bot.cogs:
                if cog_name.lower() == query.lower():
                    cog = self.bot.get_cog(cog_name)
                    break
        
        if cog:
            emoji = COG_EMOJIS.get(cog.qualified_name.lower(), "📁")
            description = COG_DESCRIPTIONS.get(cog.qualified_name.lower(), "Commands in this category")
            
            embed = discord.Embed(
                title=f"{emoji} {cog.qualified_name.title()} Commands",
                description=description,
                color=discord.Color.green()
            )
            
            commands_list = []
            for c in cog.get_commands():
                if not getattr(c, 'hidden', False) and c.enabled:
                    signature = f"{c.name} {c.signature}".strip()
                    desc = c.short_doc or "No description"
                    commands_list.append(f"`{signature}`\n└─ {desc}")

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

            embed.set_footer(text="Use f?help <command> for detailed command help")
            await ctx.send(embed=embed)
            return

        # If nothing found
        await ctx.send(
            embed=discord.Embed(
                title="❌ Not Found",
                description=f"No command or category named `{query}` was found.\n\nUse `f?help` to see all available commands.",
                color=discord.Color.red()
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
