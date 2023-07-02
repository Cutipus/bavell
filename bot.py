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

    #def on_ready(self):
    #    logging.info("Bot ready")


class Teacher(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.dictionary = Dictionary(PATH_TO_DB)
        self.users: set[int] = set()
        self.online_users: set[int] = set()
        self.user_tasks: dict[int, asyncio.Task] = dict()
        self.user_events: dict[int, asyncio.Queue] = dict()

    #@commands.Cog.listener()
    #async def on_ready(self):
    #    pass # initialize logic engine

    async def user_daemon(self, userid: int):
        self.users.add(userid)
        user: discord.User = self.bot.get_user(userid)
        task: discord.Task = None

        await user.send('Welcome to the training program.')

        try:
            while True:
                event = await self.user_events[userid].get()
                logging.debug(f"Received user event from {user.name}: {event}")
                if event == USER_ONLINE:
                    await user.send("I see you're online; Why don't we start with some questions?")
                    assert task is None
                    task = asyncio.create_task(self.interval_based(user))
                elif event == USER_OFFLINE:
                    task.cancel()
                    task = None
                    pass # stop sending messages
        except asyncio.CancelledError:
            task.cancel()
            raise
    
    async def interval_based(self, user):
        while True:
            await user.send(self.dictionary.generate_question())
            await asyncio.sleep(60)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        userid = after.id
        if userid not in self.users:
            return
        if before.status != discord.Status.online and after.status == discord.Status.online:
            if userid in self.online_users: # Discord sends two presence updates for some reason, ignoring second
                return
            self.online_users.add(userid)
            logging.info(f'{after.name} is now online')
            await self.user_events[userid].put(USER_ONLINE)
        elif before.status == discord.Status.online and after.status != discord.Status.online:
            if userid not in self.online_users: # ignoring duplicates, same as above
                return
            self.online_users.remove(userid)
            logging.info(f'{after.name} is now offline')
            await self.user_events[userid].put(USER_OFFLINE)
        else:
            return

    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f'Hello {member.name}~')

    @commands.command()
    async def register(self, ctx):
        user = ctx.author
        if user.id in self.users:
            await ctx.send(f'{user.name} is already registered.')
            return

        self.user_events[user.id] = asyncio.Queue()

        member = await commands.converter.MemberConverter().convert(ctx, str(user.id))
        if member.status == discord.Status.online:
            await self.user_events[user.id].put(USER_ONLINE)
        self.user_tasks[user.id] = asyncio.create_task(self.user_daemon(ctx.author.id))
        logging.debug(f"Added user task: {self.user_tasks[user.id]}")
        await ctx.send(f'Registered {user.name}.')
        logging.info(f"Registered {user.name} successfully.")

    @commands.command()
    async def unregister(self, ctx):
        user = ctx.author
        if user.id not in self.users:
            await ctx.send(f'{user.name} is not registered.')
            return

        self.user_tasks[user.id].cancel()
        del self.user_tasks[user.id]
        del self.user_events[user.id]
        await ctx.send(f'Unregistered {user.name}.')
        logging.info(f'Unregistered {user.name} successfully.')



async def main():
    logging.basicConfig(filename='everything.log', level=10)
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




class user:
    id = ...# user id
    profile = ...# questionaire profile - how many questions at what difficulty
    schedule = ... # when to send questionaire
    submitted_data = ...# new words, associations, pictures, sentences
    reports = ... # report for each questionaire
