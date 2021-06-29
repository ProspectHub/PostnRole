from asyncio import Lock, TimeoutError, sleep
from csv import DictWriter
from datetime import datetime
from io import StringIO
from time import time

from discord import Embed, File, Member
from discord.errors import Forbidden
from discord.ext import commands, tasks
from discord.utils import get as discord_get
from pytz import utc


def is_guild_owner():
    def predicate(ctx):
        if not ctx.guild:
            return False
        return ctx.message.author.id in [ctx.guild.owner.id, ctx.bot.owner_id]

    return commands.check(predicate)


class Counter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_count = {}
        self.lock = Lock()
        bot.loop.create_task(self.wait_for_db())

    async def wait_for_db(self):
        if not self.bot.cogs["Database"]:
            self.bot.logger.error(
                "The counter cog couldn't be loaded because the database cog is not loaded."
            )
            self.bot.unload_extension(self.__class__.__module__)
        try:
            while not self.bot.db.is_ready:
                await sleep(0.5)
        except (NameError, AttributeError):
            # The database connection wasn't made, db has been unloaded
            self.bot.logger.error("The counter cog unloaded. DB cog didn't connect.")
            return self.bot.unload_extension(self.__class__.__module__)
        self.bulk_count_update.start()
        self.bot.logger.info("The counter cog has been loaded.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if message.author.id == message.guild.owner.id:
            return
        if len(message.content.split(" ")) < 3:
            return
        if not message.guild.id in self.bot.config.counted_guilds:
            return
        async with self.lock:
            if not self.message_count.get(message.guild.id):
                self.message_count[message.guild.id] = {}
                self.message_count[message.guild.id][message.author.id] = 1
            elif not message.author.id in self.message_count[message.guild.id]:
                self.message_count[message.guild.id][message.author.id] = 1
            else:
                self.message_count[message.guild.id][message.author.id] += 1

    async def check_level_up(self, member, new_message_count: int):
        async def _add_role(member, name: str):
            try:
                await member.add_roles(
                    discord_get(member.guild.roles, name=name),
                    reason="Auto levelup role",
                )
            except Forbidden:
                bot_log = discord_get(member.guild.text_channels, name="bot-log")
                if bot_log:
                    await bot_log.send(
                        f"Couldn't level up member `{member}` due to missing permissions to {name}"
                    )

        user_active_since = (datetime.now() - member.joined_at).days
        if not discord_get(member.roles, name="Level 1") and new_message_count >= 12:
            await _add_role(member, "Level 1")
        if (
            not discord_get(member.roles, name="Level 2")
            and user_active_since > 7 * 6
            and new_message_count >= 48
        ):
            await _add_role(member, "Level 2")
        if (
            not discord_get(member.roles, name="Level 3")
            and user_active_since > 7 * 12
            and new_message_count >= 100
        ):
            await _add_role(member, "Level 3")

    @tasks.loop(seconds=30.0)
    async def bulk_count_update(self):
        while self.message_count:
            async with self.lock:
                guild_id, counts = self.message_count.popitem()
            for user_id, message_count in counts.items():
                if await self.bot.db.pool.fetchval(
                    "SELECT message_count FROM message_count WHERE guild_id=$1 AND user_id=$2",
                    guild_id,
                    user_id,
                ):
                    new_message_count = await self.bot.db.pool.fetchval(
                        "UPDATE message_count SET message_count=message_count+$1 RETURNING message_count",
                        message_count,
                    )
                else:
                    await self.bot.db.pool.execute(
                        "INSERT INTO message_count (guild_id, user_id, message_count) VALUES ($1, $2, $3) RETURNING message_count",
                        guild_id,
                        user_id,
                        message_count,
                    )
                    new_message_count = message_count
                self.bot.loop.create_task(
                    self.check_level_up(
                        self.bot.get_guild(guild_id).get_member(user_id),
                        new_message_count,
                    )
                )

    def cog_unload(self):
        self.bulk_count_update.cancel()

    @is_guild_owner()
    @commands.command(name="init", aliases=["initialize"])
    async def _init(self, ctx):
        """Initialize the bot database for the given guild."""
        if not ctx.guild.id in self.bot.config.counted_guilds:
            return await ctx.send(
                "This command is not intended to be used on this guild."
            )
        logged_channels = [
            channel
            for channel in ctx.guild.text_channels
            if channel.permissions_for(ctx.guild.me).read_messages == True
            and channel.permissions_for(ctx.guild.me).read_message_history
        ]
        confirmation_message = await ctx.send(
            f"The bot could start the logging in {len(logged_channels)} channels. Is that what you want?"
        )

        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")

        def check(reaction, member):
            return str(reaction.emoji) in ["✅", "❌"] and member == ctx.author

        try:
            reaction, member = await self.bot.wait_for(
                "reaction_add", check=check, timeout=60
            )
        except TimeoutError:
            await confirmation_message.delete()
            return await ctx.send("You didn't react within 60 seconds. Discarding...")

        if str(reaction.emoji) == "❌":
            return await confirmation_message.delete()

        self.bulk_count_update.cancel()
        await confirmation_message.remove_reaction("✅", member=ctx.guild.me)
        await confirmation_message.remove_reaction("❌", member=ctx.guild.me)
        await confirmation_message.edit(
            content="Analyzing messages. Hold tight, this will take a bit."
        )

        user_message_count = {}

        for channel in logged_channels:
            async for message in channel.history(limit=None):
                if message.author.bot:
                    continue
                if message.author.id == message.guild.owner.id:
                    continue
                if len(message.content.split(" ")) < 3:
                    continue
                if user_message_count.get(message.author.id):
                    user_message_count[message.author.id] += 1
                else:
                    user_message_count[message.author.id] = 1

        for user_id, message_count in user_message_count:
            if await self.bot.db.pool.fetchval(
                "SELECT message_count FROM message_count WHERE guild_id=$1 AND user_id=$2",
                ctx.guild.id,
                user_id,
            ):
                await self.bot.db.pool.fetchval(
                    "UPDATE message_count SET message_count=$1 RETURNING message_count",
                    message_count,
                )
            else:
                await self.bot.db.pool.execute(
                    "INSERT INTO message_count (guild_id, user_id, message_count) VALUES ($1, $2, $3) RETURNING message_count",
                    ctx.guild.id,
                    user_id,
                    message_count,
                )
            self.bot.loop.create_task(
                self.check_level_up(
                    self.bot.get_guild(ctx.guild.id).get_member(user_id), message_count
                )
            )

        await confirmation_message.delete()
        await ctx.send("The initialization has been finished!")
        self.bulk_count_update.start()

    @is_guild_owner()
    @commands.command()
    async def gencsv(self, ctx):
        """Generate a CSV table with statistics"""
        if not ctx.guild.id in self.bot.config.counted_guilds:
            return await ctx.send(
                "This command is not intended to be used on this guild."
            )
        values = await self.bot.db.pool.fetch(
            "SELECT user_id, message_count FROM message_count WHERE guild_id=$1",
            ctx.guild.id,
        )
        output = StringIO()
        writer = DictWriter(
            output, fieldnames=["user_id", "username", "joined_at", "message_count"]
        )
        writer.writeheader()
        for user_id, message_count in values:
            writer.writerow(
                {
                    "user_id": user_id,
                    "username": self.bot.get_user(user_id),
                    "joined_at": ctx.guild.get_member(user_id).joined_at.astimezone(
                        utc
                    ),
                    "message_count": message_count,
                }
            )
        output.seek(0)
        await ctx.send(
            "Find the table attached below!",
            file=File(filename=f"userdata_{int(time())}.csv", fp=output),
        )
        output.close()

    @commands.guild_only()
    @commands.command()
    async def userinfo(self, ctx, *, member: Member = None):
        """Displays information regarding a specific user"""
        if not ctx.guild.id in self.bot.config.counted_guilds:
            return await ctx.send(
                "This command is not intended to be used on this guild."
            )
        if not member:
            member = ctx.author
        message_count = await self.bot.db.pool.fetchval(
            "SELECT message_count FROM message_count WHERE guild_id=$1 AND user_id=$2",
            ctx.guild.id,
            member.id,
        )
        if not message_count:
            message_count = "not accounted"
        user_active_since = (datetime.now() - member.joined_at).days
        content = f"**Counted messages:** `{message_count}`\n**On the server for:** `{user_active_since}` days"
        embed = Embed(
            title=f"{member}'s stats",
            description=content,
            color=0x39FF14,
            timestamp=member.joined_at,
        )
        embed.set_footer(
            text="Joined:", icon_url=member.avatar_url_as(static_format="png", size=256)
        )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Counter(bot))
