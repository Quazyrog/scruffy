import os
import logging
import sys
import yaml
import discord
from discord.ext import  commands


VERSION = 2
Logger = logging.getLogger("Scruffy")
Config = {
    "ExpectedVersion": VERSION,
    "DebugMode": True,
    "LogFile":  "scruffy.log",
    "ClientSecret": None,
    "Commands": {
        "Prefix": "scruffy> "
    },
    "Greetings": {
        "Enabled": False,
        "ChannelID": None
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
        default_file.write(yaml.dump(Config))
    print(f"Default config saved to {config_file}")
    print(f"Please edit it and start bot with: python {sys.argv[0]} {config_file}")
    sys.exit(0)
with open(config_file) as cfg:
    Config.update(yaml.safe_load(cfg))
if Config["ExpectedVersion"] != VERSION:
    print("Warning: config file can be out of date for this version")

# Set up logs
log_severity_level = logging.DEBUG if Config["DebugMode"] else logging.INFO
log_formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s]  %(message)s')
log_file_handler = logging.FileHandler(Config["LogFile"])
log_file_handler.setLevel(log_severity_level)
log_file_handler.setFormatter(log_formatter)
log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(log_severity_level)
log_console_handler.setFormatter(log_formatter)
Logger.setLevel(logging.DEBUG)
Logger.addHandler(log_console_handler)
Logger.addHandler(log_file_handler)
discord_logger = logging.getLogger("discord")
discord_logger.handlers = []
discord_logger.addHandler(log_console_handler)
discord_logger.addHandler(log_file_handler)

intents = discord.Intents.default()
intents.members = True
Scruffy = commands.Bot(command_prefix=Config["Commands"]["Prefix"], intents=intents)


@Scruffy.command()
async def hello(ctx):
    Logger.debug("Executing 'hello' command")
    await ctx.send(f"Hello {ctx.author.name}! I'm Scruffy_v1.{VERSION}")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def test(ctx):
    Logger.debug("Executing 'test' command")
    await ctx.send(f"Hello {ctx.author.name} has admin permission")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def add_role(ctx, target_role: discord.Role, current_role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("This can be only issued on a server channel")
        return
    Logger.info(f"Adding role {target_role} to {current_role}")
    modified = 0
    for m in current_role.members:
        await m.add_roles(target_role)
        Logger.debug(f"Added role {target_role} to user {m}")
        modified += 1
    await ctx.send(f"Done! Granted role to {modified} server members.")


@Scruffy.command()
@commands.has_permissions(administrator=True)
async def remove_role(ctx, target_role: discord.Role, current_role: discord.Role):
    if not isinstance(ctx.author, discord.Member):
        await ctx.send("This can be only issued on a server channel")
        return
    Logger.info(f"Removing role {target_role} from {current_role}")
    modified = 0
    for m in current_role.members:
        await m.remove_roles(target_role)
        Logger.debug(f"Removed role {target_role} from user {m}")
        modified += 1
    await ctx.send(f"Done! Removed role from {modified} server members.")


@Scruffy.event
async def on_message(message):
    await Scruffy.process_commands(message)


# Run the bot
Logger.info("Scruffy reporting in!")
Scruffy.run(Config["ClientSecret"])
Logger.info("Putting Scruffy in the sleep mode, bye!")
