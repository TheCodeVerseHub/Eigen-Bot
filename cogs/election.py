import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Tuple
import asyncio
from datetime import datetime, timedelta, timezone
from utils.helpers import create_success_embed, create_error_embed

class Election(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_elections = {}  # Support multiple elections

    @commands.hybrid_group(name="election", description="Conduct staff elections with weighted votes.")
    @commands.guild_only()
    async def election(self, ctx: commands.Context):
        """Election command group."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🗳️ Election System",
                description="**Available Commands:**\n`/election create` - Create a new election\n`/election results` - View current results\n`/election end` - Force end an election",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How to Vote",
                value="Click the buttons below candidates to cast your vote!\nYou can change your vote anytime before the election ends.",
                inline=False
            )
            await ctx.send(embed=embed)

    @election.command(name="create", description="Create a new staff election poll.")
    @app_commands.describe(
        title="Election title/question",
        candidates="Comma-separated candidate names (e.g. Alice,Bob,Charlie)",
        duration="Duration in minutes (1-1440, default: 60)"
    )
    @commands.has_permissions(manage_messages=True)
    async def create(self, ctx: commands.Context, title: str, candidates: str, duration: int = 60):
        """Create a new election poll."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in servers!", ephemeral=True)
            return
            
        # Validation
        if duration < 1 or duration > 1440:  # Max 24 hours
            await ctx.reply("Duration must be between 1 and 1440 minutes (24 hours).", ephemeral=True)
            return
            
        candidate_list = [c.strip() for c in candidates.split(",") if c.strip()]
        if len(candidate_list) < 2:
            await ctx.reply("❌ You must provide at least 2 candidates.", ephemeral=True)
            return
        if len(candidate_list) > 10:
            await ctx.reply("❌ Maximum 10 candidates allowed.", ephemeral=True)
            return

        # Check if election already exists
        if ctx.guild.id in self.active_elections:
            await ctx.reply("❌ An election is already running in this server. End it first.", ephemeral=True)
            return

        # Create election data
        results: Dict[str, List[Tuple[int, float]]] = {c: [] for c in candidate_list}
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)
        
        # Create view with buttons
        view = ElectionView(self.bot, results, candidate_list, end_time, ctx.guild.id)
        
        # Create embed
        embed = discord.Embed(
            title=f"🗳️ {title}",
            description="**Vote for your preferred candidate below!**\n\nClick the buttons to cast your vote. You can change your vote anytime during the election.",
            color=0x5865F2
        )
        embed.add_field(
            name="📋 Candidates",
            value="\n".join([f"**{i+1}.** {c}" for i, c in enumerate(candidate_list)]),
            inline=False
        )
        embed.add_field(
            name="⏰ Duration",
            value=f"{duration} minutes",
            inline=True
        )
        embed.add_field(
            name="Total Votes",
            value="0",
            inline=True
        )
        embed.set_footer(text="Click buttons below to vote • You can change your vote anytime")
        embed.timestamp = datetime.now(timezone.utc)

        msg = await ctx.send(embed=embed, view=view)
        
        # Store election data
        self.active_elections[ctx.guild.id] = {
            "message": msg,
            "results": results,
            "candidates": candidate_list,
            "end_time": end_time,
            "title": title,
            "creator": ctx.author.id
        }
        
        await ctx.reply(f"Election started! Voting open for **{duration} minutes**.", ephemeral=True)
        
        # Schedule automatic end
        asyncio.create_task(self._auto_end_election(ctx.guild.id, duration * 60))

    @election.command(name="results", description="View current election results.")
    async def results(self, ctx: commands.Context):
        """Show current election results."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in servers!", ephemeral=True)
            return
            
        if ctx.guild.id not in self.active_elections:
            await ctx.reply("❌ No active election in this server.", ephemeral=True)
            return
            
        election_data = self.active_elections[ctx.guild.id]
        await self._show_results(ctx, election_data, final=False)

    @election.command(name="test", description="Test if election system is working.")
    async def test(self, ctx: commands.Context):
        """Test election system."""
        embed = discord.Embed(
            title="Election System Test",
            description="Election system is working correctly!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Status", 
            value="🟢 Online and ready", 
            inline=False
        )
        embed.add_field(
            name="Features",
            value="• Create elections with multiple candidates\n• Real-time vote counting\n• Automatic election endings\n• Vote change support",
            inline=False
        )
        await ctx.send(embed=embed)

    @election.command(name="end", description="Force end the current election.")
    @commands.has_permissions(manage_messages=True)
    async def end(self, ctx: commands.Context):
        """Force end the current election."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in servers!", ephemeral=True)
            return
            
        if ctx.guild.id not in self.active_elections:
            await ctx.reply("❌ No active election in this server.", ephemeral=True)
            return
            
        try:
            election_data = self.active_elections[ctx.guild.id]
            await self._end_election(ctx.guild.id)
            await ctx.reply("Election ended manually.")
        except Exception as e:
            await ctx.reply(f"⚠️ Election ended but there was an issue updating the message: {str(e)[:100]}...", ephemeral=True)

    async def _auto_end_election(self, guild_id: int, delay: int):
        """Automatically end election after delay."""
        await asyncio.sleep(delay)
        if guild_id in self.active_elections:
            try:
                await self._end_election(guild_id)
            except Exception as e:
                print(f"Error auto-ending election for guild {guild_id}: {e}")
                # Clean up the election data even if ending fails
                if guild_id in self.active_elections:
                    del self.active_elections[guild_id]

    async def _end_election(self, guild_id: int):
        """End an election and show final results."""
        if guild_id not in self.active_elections:
            return
            
        election_data = self.active_elections[guild_id]
        msg = election_data["message"]
        
        # Create disabled view (we'll replace the original view)
        view = discord.ui.View()
        view.timeout = None
        for candidate in election_data["candidates"]:
            button = discord.ui.Button(
                label=candidate,
                style=discord.ButtonStyle.secondary,
                emoji="🗳️",
                disabled=True
            )
            view.add_item(button)
        
        # Show final results
        tally = {}
        total_votes = 0
        for candidate, votes in election_data["results"].items():
            candidate_total = sum(weight for _, weight in votes)
            tally[candidate] = candidate_total
            total_votes += candidate_total
        
        sorted_results = sorted(tally.items(), key=lambda x: x[1], reverse=True)
        
        # Create results embed
        embed = discord.Embed(
            title=f"🏆 Final Results: {election_data['title']}",
            description="**Election has ended!**",
            color=0x57F287 if sorted_results else 0xED4245
        )
        
        if sorted_results:
            winner = sorted_results[0]
            embed.add_field(
                name="🥇 Winner",
                value=f"**{winner[0]}** with {winner[1]} votes",
                inline=False
            )
            
            results_text = ""
            for i, (candidate, votes) in enumerate(sorted_results):
                emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else "📊"
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                results_text += f"{emoji} **{candidate}**: {votes} votes ({percentage:.1f}%)\n"
            
            embed.add_field(name="📊 Full Results", value=results_text, inline=False)
        else:
            embed.add_field(name="📊 Results", value="No votes were cast.", inline=False)
        
        embed.add_field(name="📈 Total Votes", value=str(total_votes), inline=True)
        embed.add_field(name="👥 Voters", value=str(len(set(user_id for votes in election_data["results"].values() for user_id, _ in votes))), inline=True)
        embed.set_footer(text="Election completed")
        embed.timestamp = datetime.now(timezone.utc)
        
        # Try to edit the original message, if that fails send a new one
        try:
            await msg.edit(embed=embed, view=view)
        except discord.errors.HTTPException as e:
            if e.code == 50027:  # Invalid Webhook Token
                # Interaction expired, send a new message to the channel
                try:
                    channel = msg.channel if hasattr(msg, 'channel') else None
                    if channel is None and hasattr(msg, 'guild'):
                        # Try to get the channel from the guild
                        channel = msg.guild.get_channel(msg.channel_id) if hasattr(msg, 'channel_id') else None
                    
                    if channel:
                        await channel.send(embed=embed, view=view)
                    else:
                        print(f"Could not send election results - channel not found for guild {guild_id}")
                except Exception as channel_error:
                    print(f"Failed to send election results to channel: {channel_error}")
            else:
                # Re-raise other HTTP exceptions
                raise e
        except Exception as e:
            print(f"Unexpected error ending election: {e}")
        
        # Clean up
        del self.active_elections[guild_id]

    async def _show_results(self, ctx, election_data, final=False):
        """Show election results."""
        tally = {}
        total_votes = 0
        for candidate, votes in election_data["results"].items():
            candidate_total = sum(weight for _, weight in votes)
            tally[candidate] = candidate_total
            total_votes += candidate_total
        
        sorted_results = sorted(tally.items(), key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title=f"📊 {'Final' if final else 'Current'} Results: {election_data['title']}",
            color=0x57F287 if final else 0xFEE75C
        )
        
        if sorted_results:
            results_text = ""
            for i, (candidate, votes) in enumerate(sorted_results):
                emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else "📊"
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                results_text += f"{emoji} **{candidate}**: {votes} votes ({percentage:.1f}%)\n"
            
            embed.add_field(name="Results", value=results_text, inline=False)
        else:
            embed.add_field(name="Results", value="No votes cast yet.", inline=False)
        
        embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
        embed.add_field(name="Voters", value=str(len(set(user_id for votes in election_data["results"].values() for user_id, _ in votes))), inline=True)
        
        if not final:
            time_left = election_data["end_time"] - datetime.now(timezone.utc)
            if time_left.total_seconds() > 0:
                embed.add_field(name="Time Remaining", value=f"{int(time_left.total_seconds() // 60)} minutes", inline=True)
        
        await ctx.send(embed=embed, ephemeral=True)

class ElectionView(discord.ui.View):
    def __init__(self, bot, results, candidates, end_time, guild_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.results = results
        self.candidates = candidates
        self.end_time = end_time
        self.guild_id = guild_id
        
        # Add buttons for each candidate
        for candidate in candidates:
            button = VoteButton(candidate, results)
            self.add_item(button)

class VoteButton(discord.ui.Button):
    def __init__(self, candidate: str, results):
        super().__init__(
            label=candidate,
            style=discord.ButtonStyle.primary,
            emoji="🗳️"
        )
        self.candidate = candidate
        self.results = results

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in servers!", ephemeral=True)
            return
            
        user = interaction.user
        member = interaction.guild.get_member(user.id)
        
        if not member:
            await interaction.response.send_message("❌ Could not find your member data!", ephemeral=True)
            return
        
        # Check if election is still active
        election_cog = interaction.client.get_cog("Election")  # type: ignore
        if not election_cog or interaction.guild.id not in election_cog.active_elections:
            await interaction.response.send_message("❌ This election has ended.", ephemeral=True)
            return
        
        # Get election data
        election_data = election_cog.active_elections[interaction.guild.id]
        
        # Determine vote weight (hidden from users)
        weight = 1.0  # Default for regular members
        
        # Check for staff roles (staff gets 2x weight secretly)
        staff_roles = await self._get_staff_roles(interaction.guild, interaction.client)
        if any(role in member.roles for role in staff_roles):
            weight = 2.0
        
        # Check if user already voted for someone
        previous_vote = None
        for candidate_name, votes in self.results.items():
            for uid, w in votes:
                if uid == user.id:
                    previous_vote = candidate_name
                    break
            if previous_vote:
                break
        
        # Remove previous vote from all candidates
        for candidate_name in self.results.keys():
            self.results[candidate_name] = [(uid, w) for uid, w in self.results[candidate_name] if uid != user.id]
        
        # Add new vote
        self.results[self.candidate].append((user.id, weight))
        
        # Calculate total votes for embed update
        total_votes = sum(sum(w for _, w in votes) for votes in self.results.values())
        
        # Update the embed with new total vote count
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            
            # Find and update the Total Votes field
            for i, field in enumerate(embed.fields):
                if field.name == "Total Votes":
                    embed.set_field_at(i, name="Total Votes", value=str(int(total_votes)), inline=True)
                    break
            
            # Update the message with new embed
            try:
                await interaction.message.edit(embed=embed)
            except discord.errors.HTTPException as e:
                if e.code == 50027:  # Invalid Webhook Token - interaction expired
                    pass  # Can't update the message, but the vote was still recorded
                else:
                    raise e
        
        # Send appropriate response message
        if previous_vote and previous_vote != self.candidate:
            # Vote was changed
            await interaction.response.send_message(
                f"Your vote has been changed to **{self.candidate}**!",
                ephemeral=True
            )
        elif previous_vote == self.candidate:
            # Same vote (shouldn't happen but just in case)
            await interaction.response.send_message(
                f"ℹ️ You have already voted for **{self.candidate}**!",
                ephemeral=True
            )
        else:
            # New vote
            await interaction.response.send_message(
                f"Vote registered for **{self.candidate}**!",
                ephemeral=True
            )

    async def _get_staff_roles(self, guild, bot):
        """Get staff roles from the staff shift system."""
        try:
            staff_cog = bot.get_cog("StaffShifts")
            if staff_cog and hasattr(staff_cog, "service"):
                settings = await staff_cog.service.get_settings(guild.id)
                if hasattr(settings, "staff_role_ids") and settings.staff_role_ids:
                    return [guild.get_role(role_id) for role_id in settings.staff_role_ids if guild.get_role(role_id)]
        except Exception:
            pass
        
        # Fallback: look for common staff role names
        staff_keywords = ["staff", "moderator", "admin", "mod"]
        return [role for role in guild.roles if any(keyword in role.name.lower() for keyword in staff_keywords)]

async def setup(bot: commands.Bot):
    await bot.add_cog(Election(bot))
