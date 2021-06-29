import logging
from traceback import print_exc

import discord
from discord.ext import commands

import config

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(config.prefix),
    owner_id=810196248652546118,
    intents=intents,
)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
dpy_logger = logging.getLogger("discord")
dpy_logger.setLevel(logging.ERROR)


@bot.event
async def on_ready():
    print(f"{bot.user} | {len(bot.guilds)} guilds | {len(bot.users)} users seen")


@commands.is_owner()
@bot.command(hidden=True)
async def poweroff(ctx):
    """Turns off the bot"""
    await ctx.send("Bye...")
    await bot.close()


if __name__ == "__main__":
    bot.logger = logging.getLogger()
    for module in config.modules:
        try:
            bot.load_extension(f"modules.{module}")
        except:
            bot.logger.error(f"Couldn't load module: {module}")
            print_exc()
    bot.config = config
    bot.run(config.token)
