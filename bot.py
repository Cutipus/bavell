import asyncio
import os
import csv
import logging
import random
from dotenv import load_dotenv
import discord
from discord.ext import commands


USER_ONLINE = 0
USER_OFFLINE = 1

PATH_TO_DB = "dictionary.csv"

# --- logic stuff
class Dictionary:
    def __init__(self, path_to_db: str):
        self.dictionary: list[dict[str, str]] = self.load_database(path_to_db)

    def load_database(self, name: str) -> list[dict[str, str]]:
        with open(name, encoding='utf8') as db:
            reader = csv.DictReader(db, delimiter='\t')
            dictionary = []
            for line in reader:
                dictionary.append(line)
            return dictionary

    def generate_question(self):
        word = random.choice(self.dictionary)
        question = f'# {word["expression"]}      ||{word["definition"]}||'
        return question

# --- bot stuff
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)

class Teacher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.dictionary = Dictionary(PATH_TO_DB)
        self.users: dict[int, User] = dict()

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        userid = after.id
        user: User = self.users.get(userid)
        if not user:
            return

        if before.status != discord.Status.online and after.status == discord.Status.online:
            user.online.set()
        member = await commands.converter.memberconverter().convert(ctx, str(userid)) # discord.py can only fetch status for members
        if member.status == discord.Status.online:
            user.online.set()
            logging.info(f'{after.name} is now online')
        elif before.status == discord.Status.online and after.status != discord.Status.online:
            user.online.clear()
            logging.info(f'{after.name} is now offline')

    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f'Hello {member.name}~')

    @commands.command()
    async def register(self, ctx):
        userid: int = ctx.author.id
        if userid in self.users.keys():
            await ctx.send(f'{ctx.author.name} is already registered.')
            return

        user = User(ctx.author, self)
        member = await commands.MemberConverter().convert(ctx, str(userid)) # discord.py can only fetch status for members
        if member.status == discord.Status.online:
            user.online.set()

        await user.send('Welcome to the training program. Whenever you are online new exercises will be sent.')
        logging.info(f"Registered {user.name} successfully.")
        self.users[userid] = user

    @commands.command()
    async def unregister(self, ctx):
        userid: int = ctx.author.id
        if userid not in self.users.keys():
            await ctx.send(f'{ctx.author.name} is not registered.')
            return

        user = self.users[userid]
        del self.users[userid]

        await ctx.send(f'Unregistered {user.name}.')
        logging.info(f'Unregistered {user.name} successfully.')


class User:
    '''A registered user. Adds missing Status for discord.User'''
    def __init__(self, discorduser: discord.User, teacher: Teacher):
        self._discorduser = discorduser
        self.teacher = teacher

        self.interval: int = 120
        self.online: asyncio.Event = asyncio.Event()

        logging.debug("creating task")
        self.task: asyncio.Task = asyncio.create_task(self.interval_based())

    async def interval_based(self):
        logging.info('Started interval-based question daemon')
        while True:
            logging.debug('Waiting for user to come online')
            await self.online.wait()
            logging.debug('Sending question')
            await self.send(self.teacher.dictionary.generate_question())
            logging.debug('Sleeping for interval')
            await asyncio.sleep(self.interval)

    def __del__(self):
        self.task.cancel()

    def __getattr__(self, attr):
        return getattr(self._discorduser, attr)


async def main():
    #logging.basicConfig(filename='everything.log', level=10)
    logging.basicConfig(level=10)
    logging.info("Loading environment variables")
    load_dotenv()
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    logging.info("Creating bot")
    bot = Bot()

    async with bot:
        logging.info("Adding Teacher cog")
        await bot.add_cog(Teacher(bot))
        logging.info("Starting bot")
        await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
