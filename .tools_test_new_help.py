#!/usr/bin/env python
"""
Test script to validate the new interactive help cog loads properly.
"""
import asyncio
import discord
from discord.ext import commands

async def test_help_cog():
    """Simulate loading the help cog."""
    print("Creating minimal bot...")
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="f?", intents=intents, help_command=None)
    
    # Add some mock cogs to available_cogs
    bot.available_cogs = ['admin', 'economy', 'fun', 'tags', 'community']
    
    print("Loading help cog...")
    try:
        from cogs import help as help_module
        await help_module.setup(bot)
        print("✅ Help cog loaded successfully!")
        
        # Check if the cog is registered
        help_cog = bot.get_cog('HelpCog')
        if help_cog:
            print(f"✅ HelpCog registered: {help_cog}")
            
            # Check if help command exists
            help_cmd = bot.get_command('help')
            if help_cmd:
                print(f"✅ Help command registered: {help_cmd}")
            else:
                print("❌ Help command not found!")
        else:
            print("❌ HelpCog not registered!")
            
    except Exception as e:
        print(f"❌ Failed to load help cog: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_help_cog())
    exit(0 if success else 1)
