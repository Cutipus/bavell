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

logging.basicConfig(level=10)
logger = logging.getLogger('bavell')
logger.setLevel(10)
logging.getLogger('discord').setLevel(logging.WARNING)
#logging.getLogger('discord').setLevel(10)

# --- logic stuff
class Dictionary:
    def __init__(self, path_to_db: str):
        self.dictionary: dict[str, str] = dict()
        self.load_database(path_to_db)

    def load_database(self, name: str) -> dict[str, str]:
        with open(name, encoding='utf8') as db:
            reader = csv.DictReader(db, delimiter='\t')
            for row in reader:
                self.dictionary[row['expression']] = row['definition']

    def generate_question(self, word):
        question = f'# {word}    ||{self.dictionary[word]}||'
        return question

    def __getitem__(self, item):
        return self.dictionary[item]

    def words(self):
        return self.dictionary.keys()

    def definitions(self):
        return self.dictionary.values()

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

    def is_user(self, ctx: commands.Context) -> bool:
        return ctx.author.id in self.users

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        userid = after.id
        user: User = self.users.get(userid)
        if not user:
            return

        if before.status != discord.Status.online and after.status == discord.Status.online:
            user.online.set()
            logger.info(f'{after.name} is now online')
        elif before.status == discord.Status.online and after.status != discord.Status.online:
            user.online.clear()
            logger.info(f'{after.name} is now offline')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.id not in self.users:
            return
        user = self.users[user.id]
        user.add_reaction(reaction)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.id not in self.users:
            return
        user = self.users[user.id]
        user.remove_reaction(reaction)

    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        await ctx.send(f'Hello {member.name}~')

    @commands.command()
    async def register(self, ctx):
        if self.is_user(ctx):
            await ctx.send(f'{ctx.author.name} is already registered.')
            return

        user = User(ctx.author, self)
        member = await commands.MemberConverter().convert(ctx, str(user.id)) # discord.py can only fetch status for members
        if member.status == discord.Status.online:
            user.online.set()

        await user.send('Welcome to the training program. Whenever you are online new exercises will be sent.')
        logger.info(f"Registered {user.name} successfully.")
        self.users[user.id] = user

    @commands.command()
    async def unregister(self, ctx):
        if not self.is_user(ctx):
            await ctx.send(f'{ctx.author.name} is not registered.')
            return

        userid: int = ctx.author.id
        user = self.users[userid]
        del self.users[userid]
        user.close()

        await ctx.send(f'Unregistered {user.name}.')
        logger.info(f'Unregistered {user.name} successfully.')

    @commands.command()
    async def react(self, ctx):
        def check(reaction, user):  # Our check for the reaction
            return user == ctx.message.author  # We check that only the authors reaction counts

        await ctx.send("Please react to the message!")  # Message to react to

        reaction = await self.bot.wait_for("reaction_add", check=check)  # Wait for a reaction
        await ctx.send(f"You reacted with: {reaction[0]}")  # With [0] we only display the emoji


class User:
    '''A registered user. Adds missing Status for discord.User'''
    def __init__(self, discorduser: discord.User, teacher: Teacher):
        self._discorduser = discorduser
        self.teacher = teacher

        self.words: dict[str, int] = {word: 5 for word in self.teacher.dictionary.words()}
        self.messages: dict[int, str] = dict()
        self.interval: int = 120
        self.online: asyncio.Event = asyncio.Event()

        logger.debug("creating task")
        self.task: asyncio.Task = asyncio.create_task(self.interval_based())

    def add_reaction(self, reaction: discord.Reaction):
        logger.debug(f'Reaction received: {reaction.emoji} "{reaction.message.content}"')
        if reaction.emoji != '👍':
            logger.debug('Reaction not 👍; ignoring')
            return
        if reaction.message.id not in self.messages:
            logger.debug('Reaction to irrelevant message; ignoring')
            return
        word = self.messages[reaction.message.id]
        logger.debug(f'Updating {word}: {self.words[word]} -> {self.words[word] - 0.9}')
        self.words[word] -= 0.9

    def remove_reaction(self, reaction: discord.Reaction):
        logger.debug(f'Reaction removed: {reaction.emoji} "{reaction.message.content}"')
        if reaction.emoji != '👍':
            logger.debug('Reaction not 👍; ignoring')
            return
        if reaction.message.id not in self.messages:
            logger.debug('Reaction to irrelevant message; ignoring')
            return
        word = self.messages[reaction.message.id]
        logger.debug(f'Updating {word}: {self.words[word]} -> {self.words[word] + 0.9}')
        self.words[word] += 0.9

    async def interval_based(self):
        logger.info('Started interval-based question daemon')
        while True:
            logger.debug('Waiting for user to come online')
            await self.online.wait()

            logger.debug('Sending question')
            word = random.choices(list(self.words.keys()), weights=list(self.words.values()))[0]
            logger.debug(f'Chosen word: {word} [{self.words[word]}]')
            message = await self.send(self.teacher.dictionary.generate_question(word))
            await message.add_reaction('👍')
            logger.debug('Message sent')
            self.messages[message.id] = word
            self.words[word] -= 0.1

            logger.debug('Sleeping for interval')
            await asyncio.sleep(self.interval)

    def close(self):
        logger.info("Cleaning up user tasks")
        self.task.cancel()

    def __getattr__(self, attr):
        return getattr(self._discorduser, attr)


async def main():
    #logger.basicConfig(filename='everything.log', level=10)
    logger.info("Loading environment variables")
    load_dotenv()
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    logger.info("Creating bot")
    bot = Bot()

    async with bot:
        logger.info("Adding Teacher cog")
        await bot.add_cog(Teacher(bot))
        logger.info("Starting bot")
        await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
