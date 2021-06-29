from discord.ext import commands

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Returns the average of the discord websocket latency from the past one minute"""
        await ctx.send(f"The average discord websocket latency is: `{round(self.bot.latency * 1000, 2)}` ms.")

    @commands.command()
    async def source(self, ctx):
        """Returns the bot's Github page"""
        await ctx.send("<https://github.com/ProspectHub/PostnRole>")

def setup(bot):
    bot.add_cog(Misc(bot))