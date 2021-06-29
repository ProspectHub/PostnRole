from contextlib import redirect_stdout
from io import StringIO
from textwrap import indent
from traceback import format_exc

from discord.ext import commands


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    @commands.command()
    async def reload(self, ctx, *, module: str):
        """Reloads a module"""
        try:
            self.bot.reload_extension(f"modules.{module}")
        except Exception as e:
            await ctx.send(f"`ERROR:` {type(e).__name__} - {e}")
        else:
            await ctx.send("`SUCCESS`")

    @commands.command()
    async def load(self, ctx, *, module: str):
        """Loads a module"""
        try:
            self.bot.load_extension(f"modules.{module}")
        except Exception as e:
            await ctx.send(f"`ERROR:` {type(e).__name__} - {e}")
        else:
            await ctx.send("`SUCCESS`")

    @commands.command()
    async def unload(self, ctx, *, module: str):
        """Unloads a module"""
        try:
            self.bot.unload_extension(f"modules.{module}")
        except Exception as e:
            await ctx.send(f"`ERROR:` {type(e).__name__} - {e}")
        else:
            await ctx.send("`SUCCESS`")

    @commands.command(name="eval")
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_result,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = StringIO()

        to_compile = f'async def func():\n{indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{format_exc()}\n```")
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")
            else:
                self._last_result = ret
                await ctx.send(f"```py\n{value}{ret}\n```")


def setup(bot):
    bot.add_cog(Owner(bot))
