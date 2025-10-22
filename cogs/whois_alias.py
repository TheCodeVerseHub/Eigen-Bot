import discord
from discord.ext import commands
from typing import Optional

class WhoisAlias(commands.Cog):
    """Alias ?whois -> existing userinfo command (from ModerationExtended or similar)."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="whois", help="Alias for /userinfo")
    async def whois(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        # Try delegating to existing command if present
        cmd = self.bot.get_command("userinfo")
        if cmd:
            # Reinvoke existing command
            ctx.command = cmd
            await cmd.callback(cmd.cog, ctx, target)  # type: ignore
            return
        # Fallback minimal info
        embed = discord.Embed(title=f"User Info: {target}", color=discord.Color.blurple())
        embed.add_field(name="ID", value=str(target.id), inline=True)
        joined_at = getattr(target, "joined_at", None)
        embed.add_field(name="Joined", value=f"<t:{int(joined_at.timestamp())}:R>" if joined_at else "Unknown", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)
        roles_attr = getattr(target, "roles", None)
        roles = [r.mention for r in roles_attr[1:25]] if roles_attr else []
        if roles:
            embed.add_field(name="Roles", value=" ".join(roles), inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(WhoisAlias(bot))
