import discord
import discord.ext.tasks
import csv
import logging
import re
import datetime

# Config
GROUPS_FILE_IN = "dziennik.csv"
GROUPS_FILE_OUT = "dziennik-{time}.csv"
GROUPS_FIELDS = ["first_name", "last_name", "email", "group", "discord_name"]
GROUP_ROLES = {
    "1g1" : "n1g1",
    "1g2" : "n1g2",
    "1g3" : "n1g3",
    "1g4" : "n1g4",
    "1g5" : "n1g5",
    "1g6" : "n1g6",
    "1gX" : "n1gREZ",
    "asur": "Przyjaciel Scruffiego"
}
AUTOSAVE_INTERVAL_S = 60
FORCE_SAVE_TRESHOLD = 10
SERVER_NAME = "MdCŚ"
TOKEN = "NjkxNDI4NjM4NDczNTg0NjYx.Xnij6Q.sHbOp9DYskfZ3GxqcqXsmD596ZY"
CMD_AUTHORIZE = re.compile(r"authorize ((\S+@\S+[.]\S+))$")


# Misc
g_users = None
g_users_by_nick = None
g_server = None
g_n_dirty_users = 0

def check_user_fields(u, n):
    for f in GROUPS_FIELDS:
        if f not in u:
            raise RuntimeError("Failed to load users: missing field '%s' near line %i" % (f, n))

def read_users(filename):
    global g_users 
    global g_users_by_nick 
    g_users = {}
    g_users_by_nick = {}
    with open(filename) as csvfile:
        g_log.info("Reading groups from file '%s'", filename)
        reader = csv.DictReader(csvfile, skipinitialspace=True)
        header = True
        for u in reader:
            check_user_fields(u, reader.line_num)
            if u['group'] not in GROUP_ROLES:
                g_log.warning("Invalid (unmapped) group %i", reader.line_num)
            if not u["email"]:
                g_log.warning("User has no email near line %i", reader.line_num)
            if u["email"] in g_users:
                g_log.warning("Duplicate email '%s'; user '%s %s' ignored near line %i",
                                u["email"], u["first_name"], u["last_name"], reader.line_num)
            g_users[u["email"]] = u
            if (n := u["discord_name"]):
                g_users_by_nick[n] = u
        g_log.info("Loaded %i users", len(g_users))

def save_users(filename):
    global g_n_dirty_users
    if g_n_dirty_users == 0:
        pass
    with open(filename, "w") as csvfile:
        g_log.info("Saving users to file '%s'", filename)
        writer = csv.DictWriter(csvfile, GROUPS_FIELDS)
        writer.writeheader()
        for u in g_users.values():
            writer.writerow(u)
    g_log.info("Saved %i users; %i were updated", len(g_users), g_n_dirty_users)
    g_n_dirty_users = 0

def configure_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler('ScruffyLog.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s]  %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Bot stuff
g_log = configure_logger("Scruffy")
g_log.info("YAY, SCRUFFY IS STARTING!!!")
client = discord.Client()
read_users(GROUPS_FILE_IN)

@client.event
async def on_ready():
    global g_server
    g_server = discord.utils.get(client.guilds, name=SERVER_NAME)
    g_log.debug("The server is: %s", repr(g_server))
    g_log.info('%s, ready to help save %s!', client.user, g_server.name)

@client.event
async def on_message(message):
    global g_n_dirty_users
    if message.author == client.user:
        return
    if message.channel.type != discord.ChannelType.private:
        return

    if (match := CMD_AUTHORIZE.match(message.content)):
        email = match.group(1)
        member = g_server.get_member(message.author.id)
        nick = message.author.name + "#" + message.author.discriminator

        g_log.debug("Authorization request from %s<%s>", nick, email)
        if email not in g_users:
            g_log.warning("User %s<%s> is not in users base", nick, email)
            await message.channel.send("Niestety, nie mam Cię w dzienniku :(")
            return
        user = g_users[email]
        if user["discord_name"]:
            g_log.warning("User %s<%s> already authorized (email)", nick, email)
            await message.channel.send("Pamiętam, że autoryzowałem kogoś o takim mailu już wcześniej!")
            return
        if nick in g_users_by_nick:
            g_log.warning("User %s<%s> already authorized (nick)", nick, email)
            await message.channel.send("Przecież już Cię autoryzowałem!")
            return
        
        user["discord_name"] = nick
        g_n_dirty_users += 1
        g_log.debug("Authorized %s<%s> as %s %s", nick, email, user["first_name"], user["last_name"])
        # Not working: permissions error
        # await member.edit(nick=(user["first_name"] + " " + user["last_name"]))

        try:
            role = discord.utils.get(g_server.roles, name=GROUP_ROLES[user["group"]])
            g_log.debug(user["group"] + " --> " + GROUP_ROLES[user["group"]] + " --> " + str(role.id))
            await member.add_roles(role)
            g_log.debug("Assigned role %s to %s")
        except Exception as e:
            g_log.error("Failed to assign role to user %s<%s>:", nick, email, exc_info=True)
            await message.channel.send("Umm... coś nie wyszło z rolami :(")
            return

        await message.channel.send("%s, miło Cię spotkać!" % user["first_name"])
        if g_n_dirty_users >= FORCE_SAVE_TRESHOLD:
            timed_save_users()

    else:
        await message.channel.send("Nie rozumiem, czego ode mnie chcesz")

@client.event
async def on_disconned():
    timed_save_users()

@discord.ext.tasks.loop(seconds=AUTOSAVE_INTERVAL_S)
async def timed_save_users():
    try:
        time_str = datetime.datetime.now().strftime("%d-%m-%Y@%H:%M:%S")
        filename = GROUPS_FILE_OUT.format(time=time_str)
        g_log.info("Saving %s", filename)
        save_users(filename)
    except Exception as e:
        g_log.error("Failed to save %s:", filename, exc_info=True)

# This must stay at tne end!
timed_save_users.start()
client.run(TOKEN)
timed_save_users()
