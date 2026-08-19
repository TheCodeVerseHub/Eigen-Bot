import asyncio
import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.codebuddy_database import (
    get_current_week,
    get_streak_leaderboard,
    get_weekly_leaderboard,
    reset_weekly_leaderboard,
)


class CodeBuddyLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weekly_reset.start()  # Start the weekly reset task

    def cog_unload(self):
        self.weekly_reset.cancel()

    @tasks.loop(time=datetime.time(hour=0, minute=0))  # Run daily at midnight
    async def weekly_reset(self):
        """Check if it's Monday and reset weekly leaderboard if needed."""
        today = datetime.date.today()
        if today.weekday() == 0:  # Monday = 0
            await reset_weekly_leaderboard()
            print(" Weekly leaderboard reset for new week")

    @weekly_reset.before_loop
    async def before_weekly_reset(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="codeweek", description="Show the weekly coding leaderboard")
    async def codeweek(self, interaction: discord.Interaction):
        """Display the weekly leaderboard."""
        try:
            # Immediate simple response first
            embed = discord.Embed(
                title="Weekly Coding Leaderboard",
                description="Loading weekly leaderboard...",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)
            
            # Now get the actual data with timeout protection
            try:
                weekly_data = await asyncio.wait_for(get_weekly_leaderboard(10), timeout=10.0)
                week_start, week_end = get_current_week()
                weekly_list = list(weekly_data) if weekly_data else []
            except TimeoutError:
                await interaction.edit_original_response(content=" Database query timed out. Please try again.")
                return
            
            if not weekly_list:
                updated_embed = discord.Embed(
                    title="Weekly Coding Leaderboard",
                    description="No one has scored points this week yet!\nBe the first to solve some coding questions!",
                    color=0x00ff00
                )
                updated_embed.set_footer(text=f"Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
                try:
                    await interaction.edit_original_response(embed=updated_embed)
                except discord.NotFound:
                    pass
                except Exception:
                    pass
                return

            # Create final leaderboard embed
            final_embed = discord.Embed(
                title="Weekly Coding Leaderboard",
                description=f"Top coders for the week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}",
                color=0x00ff00
            )

            leaderboard_text = ""
            medals = ["1.", "2.", "3."]
            
            # Get usernames efficiently - use cached data only
            for i, (user_id, weekly_score) in enumerate(weekly_list):
                # Use only cached user data for speed
                user = interaction.guild.get_member(user_id) if interaction.guild else None
                if not user:
                    user = self.bot.get_user(user_id)
                
                # If still not found, try to fetch (fallback)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                    except Exception:
                        user = None

                username = user.display_name if user else f"<@{user_id}>"
                
                if i < 3:
                    medal = medals[i]
                else:
                    medal = f"{i+1:2d}."
                
                leaderboard_text += f"{medal} **{username}** - {weekly_score} points\n"

            final_embed.add_field(name=" Rankings", value=leaderboard_text or "No data", inline=False)
            final_embed.set_footer(text=" Solve coding questions to climb the weekly leaderboard! Resets every Monday.")
            
            # Add timeout protection for edit operation
            try:
                await interaction.edit_original_response(embed=final_embed)
            except discord.NotFound:
                pass
            except Exception:
                pass

        except discord.NotFound:
            pass  # Interaction already expired
        except Exception as e:
            print(f"[Unexpected error in codeweek command]: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(" An error occurred while fetching the weekly leaderboard.", ephemeral=True)
                else:
                    try:
                        await interaction.edit_original_response(content=" An error occurred while fetching the weekly leaderboard.")
                    except discord.NotFound:
                        pass
            except Exception:
                pass

    @commands.command(name="codeweek", aliases=["cw", "cwlb"])
    async def codeweek_prefix(self, ctx):
        """Display the weekly leaderboard."""
        try:
            # Immediate simple response first
            embed = discord.Embed(
                title="Weekly Coding Leaderboard",
                description="Loading weekly leaderboard...",
                color=0x00ff00
            )
            msg = await ctx.send(embed=embed)
            
            # Now get the actual data with timeout protection
            try:
                weekly_data = await asyncio.wait_for(get_weekly_leaderboard(10), timeout=10.0)
                week_start, week_end = get_current_week()
                weekly_list = list(weekly_data) if weekly_data else []
            except TimeoutError:
                await msg.edit(content=" Database query timed out. Please try again.")
                return
            
            if not weekly_list:
                updated_embed = discord.Embed(
                    title="Weekly Coding Leaderboard",
                    description="No one has scored points this week yet!\nBe the first to solve some coding questions!",
                    color=0x00ff00
                )
                updated_embed.set_footer(text=f"Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
                await msg.edit(embed=updated_embed)
                return

            # Create final leaderboard embed
            final_embed = discord.Embed(
                title="Weekly Coding Leaderboard",
                description=f"Top coders for the week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}",
                color=0x00ff00
            )

            leaderboard_text = ""
            medals = ["1.", "2.", "3."]
            
            # Get usernames efficiently - use cached data only
            for i, (user_id, weekly_score) in enumerate(weekly_list):
                # Use only cached user data for speed
                user = ctx.guild.get_member(user_id) if ctx.guild else None
                if not user:
                    user = self.bot.get_user(user_id)
                
                # If still not found, try to fetch (fallback)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                    except Exception:
                        user = None

                username = user.display_name if user else f"<@{user_id}>"
                
                if i < 3:
                    medal = medals[i]
                else:
                    medal = f"{i+1:2d}."
                
                leaderboard_text += f"{medal} **{username}** - {weekly_score} points\n"

            final_embed.add_field(name=" Rankings", value=leaderboard_text or "No data", inline=False)
            final_embed.set_footer(text=" Solve coding questions to climb the weekly leaderboard! Resets every Monday.")
            
            await msg.edit(embed=final_embed)

        except Exception as e:
            print(f"[Unexpected error in codeweek command]: {e}")
            await ctx.send(" An error occurred while fetching the weekly leaderboard.")

    @app_commands.command(name="codestreak", description="Show the coding streak leaderboard")
    async def codestreak(self, interaction: discord.Interaction):
        """Display the streak leaderboard."""
        try:
            # Immediate simple response first
            embed = discord.Embed(
                title=" Coding Streak Leaderboard",
                description="Loading streak leaderboard...",
                color=0xff6b35
            )
            await interaction.response.send_message(embed=embed)
            
            # Now get the actual data with timeout protection
            try:
                streak_data = await asyncio.wait_for(get_streak_leaderboard(10), timeout=10.0)
                streak_list = list(streak_data) if streak_data else []
            except TimeoutError:
                await interaction.edit_original_response(content=" Database query timed out. Please try again.")
                return
            
            if not streak_list:
                updated_embed = discord.Embed(
                    title=" Coding Streak Leaderboard",
                    description="No active streaks found!\n Solve any question correctly to start streak. ",
                    color=0xff6b35
                )
                try:
                    await interaction.edit_original_response(embed=updated_embed)
                except discord.NotFound:
                    pass
                except Exception:
                    pass
                return

            # Create final streak leaderboard embed
            final_embed = discord.Embed(
                title=" Coding Streak Leaderboard",
                description="Top coding streaks (Consecutive correct answers)",
                color=0xff6b35
            )

            leaderboard_text = ""
            medals = ["1.", "2.", "3."]
            
            # Get usernames efficiently - use cached data only
            for i, (user_id, current_streak, best_streak) in enumerate(streak_list):
                # Use only cached user data for speed
                user = interaction.guild.get_member(user_id) if interaction.guild else None
                if not user:
                    user = self.bot.get_user(user_id)
                
                # If still not found, try to fetch (fallback)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                    except Exception:
                        user = None

                username = user.display_name if user else f"<@{user_id}>"
                
                if i < 3:
                    medal = medals[i]
                else:
                    medal = f"{i+1:2d}."
                
                leaderboard_text += f"{medal} **{username}** - {current_streak} questions "
                if best_streak > current_streak:
                    leaderboard_text += f" (Best: {best_streak})"
                leaderboard_text += "\n"

            final_embed.add_field(name=" Current Streaks", value=leaderboard_text or "No data", inline=False)
            
            final_embed.add_field(
                name=" How Streaks Work", 
                value="• Answer questions correctly in a row to build your streak\n• Giving a wrong answer resets your current streak\n• Your best streak is always remembered!", 
                inline=False
            )
            final_embed.set_footer(text="Keep learning and answering questions to build an epic streak!")
            
            # Add timeout protection for edit operation
            try:
                await interaction.edit_original_response(embed=final_embed)
            except discord.NotFound:
                pass
            except Exception:
                pass

        except discord.NotFound:
            pass  # Interaction already expired
        except Exception as e:
            print(f"[Unexpected error in codestreak command]: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(" An error occurred while fetching the streak leaderboard.", ephemeral=True)
                else:
                    try:
                        await interaction.edit_original_response(content=" An error occurred while fetching the streak leaderboard.")
                    except discord.NotFound:
                        pass
            except Exception:
                pass

    @commands.command(name="codestreak", aliases=["csl", "cslb"])
    async def codestreak_prefix(self, ctx):
        """Display the streak leaderboard."""
        try:
            # Immediate simple response first
            embed = discord.Embed(
                title=" Coding Streak Leaderboard",
                description="Loading streak leaderboard...",
                color=0xff6b35
            )
            msg = await ctx.send(embed=embed)
            
            # Now get the actual data with timeout protection
            try:
                streak_data = await asyncio.wait_for(get_streak_leaderboard(10), timeout=10.0)
                streak_list = list(streak_data) if streak_data else []
            except TimeoutError:
                await msg.edit(content=" Database query timed out. Please try again.")
                return
            
            if not streak_list:
                updated_embed = discord.Embed(
                    title=" Coding Streak Leaderboard",
                    description="No active streaks found!\n Solve any question correctly to start streak. ",
                    color=0xff6b35
                )
                await msg.edit(embed=updated_embed)
                return

            # Create final streak leaderboard embed
            final_embed = discord.Embed(
                title=" Coding Streak Leaderboard",
                description="Top coding streaks (Consecutive correct answers)",
                color=0xff6b35
            )

            leaderboard_text = ""
            medals = ["1.", "2.", "3."]
            
            # Get usernames efficiently - use cached data only
            for i, (user_id, current_streak, best_streak) in enumerate(streak_list):
                # Use only cached user data for speed
                user = ctx.guild.get_member(user_id) if ctx.guild else None
                if not user:
                    user = self.bot.get_user(user_id)
                
                # If still not found, try to fetch (fallback)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                    except Exception:
                        user = None

                username = user.display_name if user else f"<@{user_id}>"
                
                if i < 3:
                    medal = medals[i]
                else:
                    medal = f"{i+1:2d}."
                
                leaderboard_text += f"{medal} **{username}** - {current_streak} questions "
                if best_streak > current_streak:
                    leaderboard_text += f" (Best: {best_streak})"
                leaderboard_text += "\n"

            final_embed.add_field(name=" Current Streaks", value=leaderboard_text or "No data", inline=False)
            
            final_embed.add_field(
                name=" How Streaks Work", 
                value="• Answer questions correctly in a row to build your streak\n• Giving a wrong answer resets your current streak\n• Your best streak is always remembered!", 
                inline=False
            )
            final_embed.set_footer(text="Keep learning and answering questions to build an epic streak!")
            
            await msg.edit(embed=final_embed)

        except Exception as e:
            print(f"[Unexpected error in codestreak command]: {e}")
            await ctx.send(" An error occurred while fetching the streak leaderboard.")

async def setup(bot):
    """Setup function to add this cog to the bot."""
    await bot.add_cog(CodeBuddyLeaderboardCog(bot))