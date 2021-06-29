from copy import copy

from discord import Embed
from discord.ext import commands


class EmbedHelp(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = Embed(description=page, color=0x39FF14)
            await destination.send(embed=embed)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.original_help = copy(self.bot.help_command)
        self.bot.help_command = EmbedHelp()

    def cog_unload(self):
        self.bot.help_command = self.original_help


def setup(bot):
    bot.add_cog(Help(bot))
