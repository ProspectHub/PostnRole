from asyncio import TimeoutError, sleep, wait_for
from traceback import format_exc

from discord.ext import commands


class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None
        bot.db = self
        self.is_ready = False
        bot.loop.create_task(self.connect_db())

    async def connect_db(self):
        try:
            from asyncpg import create_pool
        except (ImportError, ModuleNotFoundError):
            self.bot.logger.error(
                "The asyncpg database driver is not installed, db functions will be disabled."
            )
            del self.bot.db
            self.bot.unload_extension(self.__class__.__module__)
        try:
            self.pool = await create_pool(
                **self.bot.config.db_creds,
                min_size=10,
                max_size=20,
                timeout=10.0,
                command_timeout=60.0
            )
        except:
            self.bot.logger.error("Couldn't connect to database.")
            format_exc()
            del self.bot.db
            self.bot.unload_extension(self.__class__.__module__)
        else:
            await self.initialize_db()

    async def shutdown_db(self):
        async def _close_db():
            if self.pool and self.pool._initialized and not self.pool._closed:
                await self.pool.close()

        try:
            await wait_for(_close_db(), timeout=3.0)
        except TimeoutError:
            self.pool.terminate()
            del self.bot.db
            self.bot.logger.info("Database pool gracefully shut down.")

    async def initialize_db(self):
        if not await self.pool.fetchval("SELECT to_regclass('public.message_count')"):
            await self.pool.execute(
                "CREATE TABLE message_count ( user_id bigint NOT NULL, guild_id bigint NOT NULL, message_count decimal NOT NULL )"
            )
        self.is_ready = True

    def cog_unload(self):
        self.is_ready = False
        self.bot.loop.create_task(self.shutdown_db())


def setup(bot):
    bot.add_cog(Database(bot))
