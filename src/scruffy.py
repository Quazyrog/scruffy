import os
import logging
import sys
from datetime import datetime

import yaml
import discord
from discord.ext import commands
import introductions
import argparse

VERSION = 7
config = {
    "ExpectedVersion": VERSION,
    "DebugMode": True,
    "LogFile": "scruffy.log",
    "ClientSecret": None,
    "Commands": {
        "Enabled": True,
        "Prefix": "scruffy> "
    },
    "Introductions": {
        "Enabled": False,
        "Channels": [],
        "CommonRoles": [],
        "RemoveRoles": [],
        "GroupsToRolesMapping": {},
        "JournalReadPath": None,
        "JournalWritePath": None,
        "FuzzyMatchMaxLength": 0
    },
    "Censorship": {
        "Enabled": False,
        "ReactionName": "report",
        "RemoveRoles": [],
        "AddRoles": [],
        "ForwardChannel": None,
        "Channels": [],
        "Threshold": 0
    },
    "LocalizedMessages": {
        "Join.Prompt": "Hello, {user.name}!",
        "Introduction.NickUsedError": "You've already introduced!",
        "Introduction.NotInJournal": "Sorry, but you're not on the list.",
        "Introduction.Success": 'Hi, {first_name}! As member of group {group}, you were assigned roles: {roles_list}.',
        "Introduction.WrongFormat": 'Please type your name like: "Arya, Stark"; "Elon, Musk"; "Geralt, of Rivia"',
        "Censorship.ForwardedHeader": "**Message Reported**",
        "Censorship.NotificationHeader": "**Your message was reported**",
        "Censorship.Content": "Content",
        "Censorship.Time": "Time",
        "Censorship.Author": "Author",
        "Censorship.Reporter": "Reporters",
    }
}
logger = logging.getLogger("Scruffy")

# Parse command line arguments
parser = argparse.ArgumentParser()
generate_group = parser.add_mutually_exclusive_group()
generate_group.add_argument("--generate-config", action="store_true",
                            help="Generate config file for current version and exit")
generate_group.add_argument("--update-config", action="store_true",
                            help="Update old config file for current version and exit")
parser.add_argument("config_file")
commandline = parser.parse_args(sys.argv[1:])

# Load or generate config file
if commandline.generate_config:
    try:
        with open(commandline.config_file, "w") as cfg:
            cfg.write(yaml.dump(config))
    except IOError:
        print(f"Unable to write file {commandline.config_file}")
        sys.exit(1)
    print(f"Default config saved to {commandline.config_file}")
    sys.exit(0)
try:
    with open(commandline.config_file) as cfg:
        loaded_config = yaml.safe_load(cfg)
        for key, value in config.items():
            if key not in loaded_config:
                continue
            if isinstance(value, dict):
                value.update(loaded_config[key])
            else:
                config[key] = loaded_config[key]
    if config["ExpectedVersion"] != VERSION:
        print("Warning: config file can be out of date for this version")
except IOError or yaml.YAMLError or ValueError:
    print(f"Unable to read config file {commandline.config_file}")
    sys.exit(1)
if commandline.update_config:
    try:
        with open(commandline.config_file, "w") as cfg:
            cfg.write(yaml.dump(config, allow_unicode=True))
    except IOError:
        print(f"Unable to write file {commandline.config_file}")
        sys.exit(1)
    print(f"Updated config in file {commandline.config_file}")
    print(f"Still it may contain errors, so review it and set version to {VERSION}")
    sys.exit(0)

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
else:
    intro_journal = None

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
if config["Censorship"]["Enabled"]:
    intents.reactions = True
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

@Scruffy.command()
async def duck(ctx):
    await ctx.author.send("Here, take this duck!\nhttps://i.kym-cdn.com/photos/images/newsfeed/000/556/010/c40.jpg")

@Scruffy.event
async def on_member_join(member: discord.Member):
    if prompt := config["LocalizedMessages"]["Join.Prompt"]:
        await member.send(prompt.format(user=member))
        logger.debug(f"Sent prompt to {member}")


@Scruffy.event
async def on_message(message: discord.Message):
    greetings_channels = config["Introductions"]["Channels"]
    if (config["Introductions"]["Enabled"]
            and message.channel.id in greetings_channels
            and not intro_journal.is_introduced(message.author)
            and not message.is_system()):
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
    rm_roles = set(config["Introductions"]["RemoveRoles"])
    assigned = []
    removed = []
    for role in await message.guild.fetch_roles():
        if role.name in roles or role.id in roles:
            await message.author.add_roles(role)
            logger.debug(f"Assigned role {role.name}{{id={role.id}}} to {message.author}")
            assigned.append(role.name)
        if role.name in rm_roles or role.id in rm_roles:
            await message.author.remove_roles(role)
            logger.debug(f"Assigned role {role.name}{{id={role.id}}} to {message.author}")
            removed.append(role.name)
    logger.info(f"Roles added={assigned} and removed={removed} to/from member {first_name} {last_name} ({message.author})")

    notification = config["LocalizedMessages"]["Introduction.Success"] \
        .format(user=message.author, group=group, roles_list=", ".join(assigned),
                first_name=first_name, last_name=last_name)
    await message.add_reaction("🤖")
    await message.author.send(notification)


@Scruffy.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if (payload.channel_id not in config["Censorship"]["Channels"]
            or payload.emoji.name != config["Censorship"]["ReactionName"]):
        return

    channel = Scruffy.get_channel(payload.channel_id)
    reporter = Scruffy.get_user(payload.user_id)
    message = await channel.fetch_message(payload.message_id)
    logger.info(f"User '{reporter}' reported message of '{message.author}'")
    author_name = "(UnknownName)"
    if intro_journal and (name := intro_journal.name_of(message.author)):
        author_name = "%s %s" % name

    threshold = config["Censorship"]["Threshold"]
    reporters = []
    if threshold > 1:
        for reaction in message.reactions:
            if reaction.emoji.name == config["Censorship"]["ReactionName"] \
                    and reaction.count >= threshold:
                for user in await reaction.users().flatten():
                    reporters.append(user.id)
                break
        else:
            logger.debug("Reports number still below threshold")
            return
        logger.info(f"Message of user '{message.author}' reported {threshold} times; executing due procedures...")


    try:
        roles_to_remove = config["Censorship"]["RemoveRoles"]
        removed = 0
        for role in message.author.roles:
            if role.id in roles_to_remove or role.name in roles_to_remove:
                await message.author.remove_roles(role)
                removed += 1
        logger.debug(f"Removed {removed} roles from '{message.author}'")
    except discord.errors.Forbidden:
        logger.debug(f"Could not properly punish '{message.author}': privilege error!")

    try:
        for role in config["Censorship"]["AddRoles"]:
            await message.author.add_roles(message.guild.get_role(role))
    except discord.errors.Forbidden:
        logger.debug(f"Could not properly punish '{message.author}': privilege error!")

    async def send_notification(target_channel, text):
        forward_files = []
        for attachment in message.attachments:
            forward_files.append(await attachment.to_file())
        await target_channel.send(text, files=forward_files)

    quoted_content = "> " + message.content.replace("\n", "\n> ")
    await send_notification(message.author, f"""{config["LocalizedMessages"]["Censorship.NotificationHeader"]}
{config["LocalizedMessages"]["Censorship.Time"]}: {datetime.now().isoformat()}
{config["LocalizedMessages"]["Censorship.Author"]}: {author_name} <@{message.author.id}>
{config["LocalizedMessages"]["Censorship.Content"]}: 
{quoted_content}""")
    forward_channel = Scruffy.get_channel(config["Censorship"]["ForwardChannel"])
    reporters = ", ".join("<@%i>" % r for r in reporters)
    await send_notification(forward_channel, f"""{config["LocalizedMessages"]["Censorship.ForwardedHeader"]}
{config["LocalizedMessages"]["Censorship.Time"]}: {datetime.now().isoformat()}
{config["LocalizedMessages"]["Censorship.Author"]}: {author_name} <@{message.author.id}>
{config["LocalizedMessages"]["Censorship.Reporter"]}: {reporters}
{config["LocalizedMessages"]["Censorship.Content"]}: 
{quoted_content}""")
    await message.delete()
# END on_raw_reaction_add


# Run the bot
logger.info("Scruffy reporting in!")
Scruffy.run(config["ClientSecret"])
if intro_journal and (path := config["Introductions"]["JournalWritePath"]):
    intro_journal.save(path)
    logger.info(f"Saved introduction journal to {path}")
logger.info("Putting Scruffy in the sleep mode, bye!")
