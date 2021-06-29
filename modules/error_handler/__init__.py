from asyncio import TimeoutError
from datetime import timedelta
from sys import stderr
from traceback import print_tb

from aiohttp import ClientOSError, ContentTypeError, ServerDisconnectedError
from discord import HTTPException
from discord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            # command has its own error handler
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.BadArgument):
            if isinstance(error, commands.MemberNotFound):
                await ctx.send("The member you referenced was not found.")
            elif isinstance(error, commands.GuildNotFound):
                await ctx.send("The guild you referenced was not found.")
            elif isinstance(error, commands.UserNotFound):
                await ctx.send("The user you referenced was not found.")
            elif isinstance(error, commands.ChannelNotFound):
                await ctx.send("The channel you referenced was not found.")
            else:
                await ctx.send(
                    "You have used an invalid argument for the given command."
                )
        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(
                f"You are being rate-limited on that command. Please wait `{timedelta(seconds=int(error.retry_after))}` seconds before using the command!"
            )

        elif hasattr(error, "original") and isinstance(error.original, HTTPException):
            return
        elif isinstance(error, commands.NotOwner):
            return await ctx.send("This command is only available to the bot owner!")
        elif isinstance(error, commands.CheckFailure):
            return await ctx.send("This command is meant for other users.")
        elif isinstance(error, commands.CommandInvokeError) and hasattr(
            error, "original"
        ):
            if isinstance(
                error.original,
                (
                    ClientOSError,
                    ServerDisconnectedError,
                    ContentTypeError,
                    TimeoutError,
                ),
            ):
                # Called on 500 HTTP responses
                # TimeoutError: A Discord operation timed out. All others should be handled by us
                return
            print("In {}:".format(ctx.command.qualified_name), file=stderr)
            print_tb(error.original.__traceback__)
            print(
                "{0}: {1}".format(error.original.__class__.__name__, error.original),
                file=stderr,
            )


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
