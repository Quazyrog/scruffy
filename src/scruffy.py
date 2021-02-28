import os
import logging
import sys
import yaml
import discord
from discord.ext import commands
import introductions


VERSION = 4
logger = logging.getLogger("Scruffy")
config = {
    "ExpectedVersion": VERSION,
    "DebugMode": True,
    "LogFile":  "scruffy.log",
    "ClientSecret": None,
    "Commands": {
        "Enabled": True,
        "Prefix": "scruffy> "
    },
    "Introductions": {
        "Enabled": False,
        "ChannelId": None,
        "CommonRoles": [],
        "GroupsToRolesMapping": {},
        "JournalReadPath": None,
        "JournalWritePath": None,
        "FuzzyMatchMaxLength": 0
    },
    "LocalizedMessages": {
        "Join.Prompt": "Hello, {user.name}!",
        "Introduction.NickUsedError": "You've already introduced!",
        "Introduction.NotInJournal": "Sorry, but you're not on the list.",
        "Introduction.WrongFormat": 'Please type your name like: "Arya, Stark"; "Elon, Musk"; "Geralt, of Rivia"'
    }
}


# Load or generate config file
if len(sys.argv) > 2:
    print(f"Usage: python {sys.argv[0]} [ConfigFile]")
    sys.exit(1)
config_file = sys.argv[1] if len(sys.argv) == 2 else ""
if not os.path.isfile(config_file):
    config_file = config_file or "scruffy-settings.yml"
    with open(config_file, "w") as default_file:
        default_file.write(yaml.dump(config))
    print(f"Default config saved to {config_file}")
    print(f"Please edit it and start bot with: python {sys.argv[0]} {config_file}")
    sys.exit(0)
with open(config_file) as cfg:
    config.update(yaml.safe_load(cfg))
if config["ExpectedVersion"] != VERSION:
    print("Warning: config file can be out of date for this version")

# Set up logs
log_severity_level = logging.DEBUG if config["DebugMode"] else logging.INFO
log_formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s]  %(message)s')
log_file_handler = logging.FileHandler(config["LogFile"])
log_file_handler.setLevel(log_severity_level)
log_file_handler.setFormatter(log_formatter)
log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(log_severity_level)
log_console_handler.setFormatter(log_formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(log_console_handler)
logger.addHandler(log_file_handler)
discord_logger = logging.getLogger("discord")
discord_logger.handlers = []
discord_logger.addHandler(log_console_handler)
discord_logger.addHandler(log_file_handler)

# Read journal for introductions
if config["Introductions"]["Enabled"]:
    intro_journal = introductions.Journal()
    intro_journal.read(config["Introductions"]["JournalReadPath"])


intents = discord.Intents.default()
intents.members = True
Scruffy = commands.Bot(command_prefix=config["Commands"]["Prefix"], intents=intents)


@Scruffy.command()
async def hello(ctx):
    logger.debug("Executing 'hello' command")
    await ctx.send(f"Hello {ctx.author.name}! I'm **Scruffy_v1.{VERSION}**")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def test(ctx):
    logger.debug("Executing 'test' command")
    await ctx.send(f"Hello {ctx.author.name} has admin permission")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def add_role(ctx, target_role: discord.Role, current_role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("This can be only issued on a server channel")
        return
    logger.info(f"Adding role {target_role} to {current_role}")
    modified = 0
    for m in current_role.members:
        await m.add_roles(target_role)
        logger.debug(f"Added role {target_role} to user {m}")
        modified += 1
    await ctx.send(f"Done! Granted role to {modified} server members.")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def remove_role(ctx, target_role: discord.Role, current_role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("This can be only issued on a server channel")
        return
    logger.info(f"Removing role {target_role} from {current_role}")
    modified = 0
    for m in current_role.members:
        await m.remove_roles(target_role)
        logger.debug(f"Removed role {target_role} from user {m}")
        modified += 1
    await ctx.send(f"Done! Removed role from {modified} server members.")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def write_introduction_journal(ctx):
    if file := config["Introductions"]["JournalWritePath"]:
        intro_journal.save(file)
        logger.info(f"Saved updated journal to {file}")


@Scruffy.event
async def on_member_join(member: discord.Member):
    if prompt := config["LocalizedMessages"]["Join.Prompt"]:
        await member.send(prompt.format(user=member))
        logger.debug(f"Sent prompt to {member}")


@Scruffy.event
async def on_message(message: discord.Message):
    if (config["Introductions"]["Enabled"]
            and message.channel.id == config["Introductions"]["Channel"]
            and not intro_journal.is_introduced(message.author)):
        await handle_introduction(message)
    await Scruffy.process_commands(message)


async def handle_introduction(message):
    logger.debug(f"Introduction received")
    try:
        first_name, last_name = list(x.strip() for x in message.content.split(",", maxsplit=1))
    except ValueError:
        await message.author.send(config["LocalizedMessages"]["Introduction.WrongFormat"])
        return

    # Extract group and find user in journal
    group = None
    try:
        limit_len = config["Introductions"]["FuzzyMatchMaxLength"]
        if len(first_name) <= limit_len and len(last_name) <= limit_len:
            group = intro_journal.match_name_weak(first_name, last_name, message.author.id)
        else:
            group = intro_journal.match_name(first_name, last_name, message.author.id)
    except introductions.NickInUseError:
        logger.warning(f"Member {message.author} tried to introduce twice")
        await message.author.send(config["LocalizedMessages"]["Introduction.NickUsedError"])
        return

    # Select roles to assign
    roles = set(config["Introductions"]["CommonRoles"])
    if not group:
        await message.author.send(config["LocalizedMessages"]["Introduction.NotInJournal"])
        logger.warning(f"Member {message.author} ({first_name} {last_name}) not found in journal")
        return
    if group in config["Introductions"]["GroupsToRolesMapping"]:
        roles.update(config["Introductions"]["GroupsToRolesMapping"][group])
    else:
        logger.warning(f"Group {group} has no roles assigned")

    # Change nickname; this may fail for admins
    try:
        await message.author.edit(nick=f"{first_name} {last_name}")
    except discord.errors.Forbidden:
        logger.warning(f"Permission error when trying to set nickname for {message.author.name}; is it an admin?")

    # Assign roles
    assigned = []
    for role in await message.guild.fetch_roles():
        if role.name in roles or role.id in roles:
            await message.author.add_roles(role)
            logger.debug(f"Assigned role {role.name}{{id={role.id}}} to {message.author}")
            assigned.append(role.name)
    if len(assigned) < len(roles):
        logger.warning(f"Not all roles {roles} for {message.author} found in the server ({len(assigned)}/{len(roles)})")
    else:
        logger.info(f"Assigned roles {roles} to member {first_name} {last_name} ({message.author})")

    notification = config["LocalizedMessages"]["Introduction.Success"] \
        .format(user=message.author, group=group, roles_list=", ".join(assigned),
                first_name=first_name, last_name=last_name)
    await message.add_reaction("🤖")
    await message.author.send(notification)


# Run the bot
logger.info("Scruffy reporting in!")
Scruffy.run(config["ClientSecret"])
logger.info("Putting Scruffy in the sleep mode, bye!")
