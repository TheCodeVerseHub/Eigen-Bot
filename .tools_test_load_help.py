import asyncio
import discord
from discord.ext import commands

# Minimal Config-like object
class Cfg:
    discord_token = None
    database_url = 'sqlite+aiosqlite:///test.db'
    guild_id = None

async def main():
    bot = commands.Bot(command_prefix='f?', intents=discord.Intents.default(), help_command=None)
    # Manually import and run the setup from the help cog
    from cogs import help as help_cog
    await help_cog.setup(bot)
    print('Help cog setup completed; commands:', [c.name for c in bot.commands])
    await bot.close()

if __name__ == '__main__':
    asyncio.run(main())
