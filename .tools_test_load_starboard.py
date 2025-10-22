import asyncio
import discord
from discord.ext import commands

async def main():
    bot = commands.Bot(command_prefix='f?', intents=discord.Intents.default(), help_command=None)
    try:
        from cogs import starboard as starboard_cog
        await starboard_cog.setup(bot)
        print('Starboard cog setup completed; commands:', [c.name for c in bot.commands])
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await bot.close()

if __name__ == '__main__':
    asyncio.run(main())
