
import aiosqlite
import discord
from discord.ext import commands

from utils.codebuddy_database import DB_PATH


class TODView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Truth", style=discord.ButtonStyle.secondary, custom_id="tod_truth")
    async def truth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_tod(interaction, "truth")

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.secondary, custom_id="tod_dare")
    async def dare_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_tod(interaction, "dare")

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, custom_id="tod_random")
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_tod(interaction, "random")

    async def send_tod(self, interaction: discord.Interaction, type_choice: str):
        async with aiosqlite.connect(DB_PATH) as db:
            if type_choice == "random":
                query = "SELECT type, question, rating FROM tod_questions ORDER BY RANDOM() LIMIT 1"
                args = ()
            else:
                query = "SELECT type, question, rating FROM tod_questions WHERE type = ? ORDER BY RANDOM() LIMIT 1"
                args = (type_choice,)
            
            async with db.execute(query, args) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message("No questions found in database!", ephemeral=True)
            return

        q_type, question, rating = row
        
        color = discord.Color(0x00ff00) if q_type == "truth" else discord.Color(0xff0000)
        
        embed = discord.Embed(
            description=f"**{question}**",
            color=color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Type: {q_type.capitalize()} | Rating: {rating}")
        
        await interaction.response.send_message(embed=embed, view=TODView())

class TOD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_tod(self, type_choice: str):
        async with aiosqlite.connect(DB_PATH) as db:
            if type_choice == "random":
                query = "SELECT type, question, rating FROM tod_questions ORDER BY RANDOM() LIMIT 1"
                args = ()
            else:
                query = "SELECT type, question, rating FROM tod_questions WHERE type = ? ORDER BY RANDOM() LIMIT 1"
                args = (type_choice,)
            
            async with db.execute(query, args) as cursor:
                return await cursor.fetchone()

    async def send_tod_message(self, ctx, type_choice: str):
        row = await self.get_tod(type_choice)
        
        if not row:
            await ctx.send("No questions found in database!")
            return

        q_type, question, rating = row
        
        color = discord.Color(0x00ff00) if q_type == "truth" else discord.Color(0xff0000)
        
        embed = discord.Embed(
            description=f"**{question}**",
            color=color
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Type: {q_type.capitalize()} | Rating: {rating}")
        
        await ctx.send(embed=embed, view=TODView())

    @commands.hybrid_command(name="tod", description="Play Truth or Dare")
    async def tod_command(self, ctx: commands.Context):
        await self.send_tod_message(ctx, "random")

    @commands.command(name="truth")
    async def truth_command(self, ctx: commands.Context):
        await self.send_tod_message(ctx, "truth")

    @commands.command(name="dare")
    async def dare_command(self, ctx: commands.Context):
        await self.send_tod_message(ctx, "dare")

async def setup(bot):
    await bot.add_cog(TOD(bot))
