import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class HelpCog(commands.Cog):
    """Professional, emoji-free help command.

    Provides a tidy list of cogs/commands and a detailed view for a single command or cog.
    Works as a hybrid command so both prefix (`f?help`) and slash (`/help`) are available.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show help for commands or a specific command/cog")
    @app_commands.describe(query="Optional command or cog name to show detailed help for")
    async def help(self, ctx: commands.Context, *, query: Optional[str] = None):
        # If a specific command or cog name was provided, show detailed help
        if query:
            await self._detailed_help(ctx, query)
            return

        # General help: list cogs and their visible commands
        embed = discord.Embed(title="Help: Commands", color=discord.Color.blue())
        embed.description = (
            "Use `f?help <command>` or `/help <command>` for detailed help on a command.\n"
            "Use `f?help <cog>` or `/help <cog>` to see commands in a category."
        )

        # Build a map of cog name -> list of command signatures
        # Use the bot's discovered available cogs to maintain consistent ordering
        available = getattr(self.bot, 'available_cogs', list(self.bot.cogs.keys()))
        for cog_name in available:
            # Display loaded cogs with their commands; otherwise mark as not loaded
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                embed.add_field(name=cog_name, value="Not loaded", inline=False)
                continue

            # Skip the help cog itself
            if cog_name == 'help':
                continue

            visible_cmds = []
            for cmd in cog.get_commands():
                if not getattr(cmd, 'hidden', False) and cmd.enabled:
                    signature = f"{cmd.name} {cmd.signature}".strip()
                    visible_cmds.append(f"`{signature}` - {cmd.short_doc or 'No description.'}")

            if visible_cmds:
                embed.add_field(name=cog_name, value="\n".join(visible_cmds), inline=False)

        # Also include any top-level commands not in cogs
        top_level = []
        for cmd in self.bot.commands:
            if cmd.cog is None and not getattr(cmd, 'hidden', False) and cmd.enabled:
                top_level.append(f"`{cmd.name} {cmd.signature}` - {cmd.short_doc or 'No description.'}")

        if top_level:
            embed.add_field(name="General Commands", value="\n".join(top_level), inline=False)

        embed.set_footer(text="Use the help command with a command name for more detail.")
        await ctx.send(embed=embed)

    async def _detailed_help(self, ctx: commands.Context, query: str):
        # Try to find a command first
        cmd = self.bot.get_command(query)
        if cmd:
            embed = discord.Embed(title=f"Help: {cmd.qualified_name}", color=discord.Color.blue())
            embed.add_field(name="Signature", value=f"`{cmd.qualified_name} {cmd.signature}`", inline=False)
            embed.add_field(name="Description", value=cmd.help or cmd.short_doc or "No description.", inline=False)
            perms = getattr(cmd, '__cog_commands_permissions__', None)
            await ctx.send(embed=embed)
            return

        # Try to find a cog
        cog = self.bot.get_cog(query)
        if cog:
            embed = discord.Embed(title=f"Category: {cog.qualified_name}", color=discord.Color.blue())
            commands_list = []
            for c in cog.get_commands():
                if not getattr(c, 'hidden', False) and c.enabled:
                    commands_list.append(f"`{c.name} {c.signature}` - {c.short_doc or 'No description.'}")

            if commands_list:
                embed.add_field(name="Commands", value="\n".join(commands_list), inline=False)
            else:
                embed.description = "No visible commands in this category."

            await ctx.send(embed=embed)
            return

        # If nothing found
        await ctx.send(embed=discord.Embed(title="Help: Not found", description=f"No command or category named '{query}' found.", color=discord.Color.red()))


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
