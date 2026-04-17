import discord
from discord.ext import commands
from discord import app_commands

class CodeBuddyHelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="codehelp", description="Get help and information about CodeBuddy bot commands")
    async def help_command(self, interaction: discord.Interaction):
        """Displays help information about all available commands."""
        
        # Send immediate response to prevent timeout (non-ephemeral so everyone can see)
        await interaction.response.send_message("Loading help information...")
        
        # Create main help embed
        embed = discord.Embed(
            title=" CodeBuddy Help",
            description="Welcome to CodeBuddy! Here are all available commands and features:",
            color=discord.Color.blue()
        )
        
        # Add bot information
        embed.add_field(
            name=" About CodeBuddy",
            value="CodeBuddy is an interactive coding quiz bot that posts questions every 20 minutes. "
                  "Answer with 'a', 'b', or 'c' to earn points and build streaks!",
            inline=False
        )
        
        # Quiz Commands
        embed.add_field(
            name=" Leaderboard Commands",
            value=(
                "`/codeleaderboard` (or `?clb`) - View the overall leaderboard (all-time top performers)\n"
                "`/codeweek` (or `?cw`) - View weekly leaderboard (resets every Monday)\n"
                "`/codestreak` (or `?cs`) - View streak leaderboard (current and best streaks)"
            ),
            inline=False
        )
        
        # Personal Commands
        embed.add_field(
            name=" Personal Stats Commands",
            value=(
                "`/codestats` (or `?cst`) - View your personal statistics and performance\n"
                "`/codeflex` (or `?cfl`) - Generate a beautiful visual profile card with your stats"
            ),
            inline=False
        )
        
        # How to Play
        embed.add_field(
            name=" How to Play",
            value=(
                "1. Wait for quiz questions (posted every 20 minutes)\n"
                "2. Answer quickly with `a`, `b`, or `c`\n"
                "3. Build streaks by answering consecutively\n"
                "4. Watch out for **BONUS** questions (double points!)\n"
                "5. Compete on weekly and overall leaderboards"
            ),
            inline=False
        )
        
        # Scoring System
        embed.add_field(
            name=" Scoring System",
            value=(
                "• **Correct Answer**: +1 point\n"
                "• **Bonus Question**: +2 points\n"
                "• **Wrong Answer**: Streak resets to 0\n"
                "• **Streaks**: Track consecutive correct answers"
            ),
            inline=False
        )
        
        # Additional Features
        embed.add_field(
            name=" Special Features",
            value=(
                "• **Weekly Reset**: Leaderboards reset every Monday\n"
                "• **Visual Cards**: Custom profile cards with gradient text\n"
                "• **Streak Tracking**: Current streaks and personal bests\n"
                "• **Fair Play**: One answer per question per user"
            ),
            inline=False
        )
        
        # Footer
        embed.set_footer(text="Need more help? Ask in the server or check our GitHub!")
        
        # Create buttons for additional help
        view = HelpButtonView()
        
        # Edit the original response with the help embed
        await interaction.edit_original_response(content=None, embed=embed, view=view)

    @commands.command(name="quizhelp", help="Get help and information about CodeBuddy bot commands")
    async def quizhelp_prefix(self, ctx):
        """Displays help information about all available commands."""
        
        # Send immediate response to prevent timeout
        msg = await ctx.send("Loading help information...")
        
        # Create main help embed
        embed = discord.Embed(
            title=" CodeBuddy Help",
            description="Welcome to CodeBuddy! Here are all available commands and features:",
            color=discord.Color.blue()
        )
        
        # Add bot information
        embed.add_field(
            name=" About CodeBuddy",
            value="CodeBuddy is an interactive coding quiz bot that posts questions every 20 minutes. "
                  "Answer with 'a', 'b', or 'c' to earn points and build streaks!",
            inline=False
        )
        
        # Quiz Commands
        embed.add_field(
            name=" Leaderboard Commands",
            value=(
                "`/codeleaderboard` (or `?clb`) - View the overall leaderboard (all-time top performers)\n"
                "`/codeweek` (or `?cw`) - View weekly leaderboard (resets every Monday)\n"
                "`/codestreak` (or `?cs`) - View streak leaderboard (current and best streaks)"
            ),
            inline=False
        )
        
        # Personal Commands
        embed.add_field(
            name=" Personal Stats Commands",
            value=(
                "`/codestats` (or `?cst`) - View your personal statistics and performance\n"
                "`/codeflex` (or `?cfl`) - Generate a beautiful visual profile card with your stats"
            ),
            inline=False
        )
        
        # How to Play
        embed.add_field(
            name=" How to Play",
            value=(
                "1. Wait for quiz questions (posted every 20 minutes)\n"
                "2. Answer quickly with `a`, `b`, or `c`\n"
                "3. Build streaks by answering consecutively\n"
                "4. Watch out for **BONUS** questions (double points!)\n"
                "5. Compete on weekly and overall leaderboards"
            ),
            inline=False
        )
        
        # Scoring System
        embed.add_field(
            name=" Scoring System",
            value=(
                "• **Correct Answer**: +1 point\n"
                "• **Bonus Question**: +2 points\n"
                "• **Wrong Answer**: Streak resets to 0\n"
                "• **Streaks**: Track consecutive correct answers"
            ),
            inline=False
        )
        
        # Additional Features
        embed.add_field(
            name=" Special Features",
            value=(
                "• **Weekly Reset**: Leaderboards reset every Monday\n"
                "• **Visual Cards**: Custom profile cards with gradient text\n"
                "• **Streak Tracking**: Current streaks and personal bests\n"
                "• **Fair Play**: One answer per question per user"
            ),
            inline=False
        )
        
        # Footer
        embed.set_footer(text="Need more help? Ask in the server or check our GitHub!")
        
        # Create buttons for additional help
        view = HelpButtonView()
        
        # Edit the original response with the help embed
        await msg.edit(content=None, embed=embed, view=view)

class HelpButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
    
    @discord.ui.button(label=" Leaderboards", style=discord.ButtonStyle.primary)
    async def leaderboard_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=" Leaderboard Commands",
            description="Detailed information about leaderboard commands",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="/codeleaderboard",
            value=(
                "**Description**: Overall leaderboard with all-time top performers\n"
                "**Shows**: Top 10 users by total points\n"
                "**Includes**: Total points, current streak, rank position"
            ),
            inline=False
        )
        
        embed.add_field(
            name="/codeweek", 
            value=(
                "**Description**: Weekly leaderboard that resets every Monday\n"
                "**Shows**: Top 10 users for current week\n"
                "**Reset**: Automatic every Monday at midnight UTC"
            ),
            inline=False
        )
        
        embed.add_field(
            name="/codestreak",
            value=(
                "**Description**: Streak-focused leaderboard\n"
                "**Shows**: Current streaks and all-time best streaks\n"
                "**Note**: Streaks reset on wrong answers"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label=" Personal Stats", style=discord.ButtonStyle.secondary)
    async def stats_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=" Personal Statistics",
            description="Information about personal stat commands",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="/codestats",
            value=(
                "**Shows your personal statistics:**\n"
                "• Total correct answers\n"
                "• Current streak\n" 
                "• Best streak ever\n"
                "• Your rank position\n"
                "• Points to next rank"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label=" Game Rules", style=discord.ButtonStyle.success)
    async def rules_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=" Game Rules & Tips",
            description="Everything you need to know about playing CodeBuddy",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name=" Basic Rules",
            value=(
                "• Questions appear every 20 minutes\n"
                "• Answer with `a`, `b`, or `c` only\n"
                "• One answer per question per user\n"
                "• Case insensitive (A, a, B, b, etc. all work)"
            ),
            inline=False
        )
        
        embed.add_field(
            name=" Bonus Questions",
            value=(
                "• 10% chance for bonus questions\n"
                "• Worth **2 points** instead of 1\n"
                "• Look for the BONUS indicator\n"
                "• Same rules apply"
            ),
            inline=False
        )
        
        embed.add_field(
            name=" Streaks",
            value=(
                "• Build streaks with consecutive correct answers\n"
                "• Reset to 0 on wrong answers\n"
                "• Track both current and best streaks\n"
                "• Show off on the streak leaderboard!"
            ),
            inline=False
        )
        
        embed.add_field(
            name=" Competition",
            value=(
                "• Compete on overall leaderboard (all-time)\n"
                "• Weekly competitions reset Monday\n"
                "• Streak competitions for consecutive answers\n"
                "• Check your rank anytime with `/codestats`"
            ),
            inline=False
        )
        
        embed.add_field(
            name=" Pro Tips",
            value=(
                "• Be quick but careful with answers\n"
                "• Use `/codestats` to track progress\n"
                "• Join during bonus questions for extra points\n"
                "• Build streaks for leaderboard dominance"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label=" FAQ", style=discord.ButtonStyle.danger)
    async def faq_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=" Frequently Asked Questions",
            description="Common questions and answers",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Q: When do questions appear?",
            value="A: Every 20 minutes automatically. No manual posting required!",
            inline=False
        )
        
        embed.add_field(
            name="Q: Can I answer multiple times?",
            value="A: No, you can only answer once per question to ensure fair play.",
            inline=False
        )
        
        embed.add_field(
            name="Q: When do weekly leaderboards reset?",
            value="A: Every Monday at midnight UTC. Your weekly progress starts fresh!",
            inline=False
        )
        
        embed.add_field(
            name="Q: How are bonus questions chosen?",
            value="A: Completely random! There's a 10% chance any question will be a bonus.",
            inline=False
        )
        
        embed.add_field(
            name="Q: What happens if I get a wrong answer?",
            value="A: Your current streak resets to 0, but your total points remain unchanged.",
            inline=False
        )
        
        embed.add_field(
            name="Q: Can I see other players' detailed stats?",
            value="A: Only through leaderboards. Use `/codestats` for your personal detailed stats.",
            inline=False
        )
        
        embed.add_field(
            name="Q: Are the questions always the same difficulty?",
            value="A: Questions vary in difficulty and cover different coding topics and concepts.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def on_timeout(self):
        # Disable all buttons when the view times out
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

async def setup(bot: commands.Bot):
    """Set up the help cog."""
    await bot.add_cog(CodeBuddyHelpCog(bot))
    print("+> Help cog loaded successfully!")