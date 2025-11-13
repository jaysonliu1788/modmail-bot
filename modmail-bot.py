import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os

# ------------------------
# Load environment
# ------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_GUILD_ID = int(os.getenv("STAFF_GUILD_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ACTIVE_ID = int(os.getenv("CATEGORY_ACTIVE_ID"))
ARCHIVE_ID = int(os.getenv("CATEGORY_ARCHIVE_ID"))
CLOSED_ID = int(os.getenv("CATEGORY_CLOSED_ID"))
CLAIMED_ID = int(os.getenv("CATEGORY_CLAIMED_ID"))
PREFIX = os.getenv("PREFIX", "?")

# ------------------------
# Bot setup
# ------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

active_threads = {}  # user_id -> channel_id
claimed_threads = {} # channel_id -> staff_id

# ------------------------
# Ready
# ------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()
    print("Slash commands synced")

# ------------------------
# DM handler
# ------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        guild = bot.get_guild(STAFF_GUILD_ID)
        category = discord.utils.get(guild.categories, id=ACTIVE_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        # Create new thread
        if message.author.id not in active_threads:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False)
            }
            channel = await guild.create_text_channel(
                name=f"modmail-{message.author.name}",
                category=category,
                overwrites=overwrites,
                topic=f"ModMail for {message.author} ({message.author.id})"
            )
            active_threads[message.author.id] = channel.id

            embed_open = discord.Embed(
                title="📬 New ModMail Opened",
                description=f"**User:** {message.author} ({message.author.id})",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed_open)
            if log_channel:
                await log_channel.send(embed=embed_open)

            await message.author.send(embed=discord.Embed(
                title="ModMail Opened",
                description="Your message has been sent to the staff team.",
                color=discord.Color.green()
            ))

        # Forward user message
        channel = guild.get_channel(active_threads[message.author.id])
        if channel:
            embed = discord.Embed(description=message.content, color=discord.Color.blurple())
            embed.set_author(name=message.author, icon_url=message.author.display_avatar)
            await channel.send(embed=embed)

    await bot.process_commands(message)

# ------------------------
# ?reply (prefix)
# ------------------------
@bot.command(name="reply")
async def reply_cmd(ctx, user_id: int, *, message):
    user = await bot.fetch_user(user_id)
    embed = discord.Embed(description=message, color=discord.Color.green())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar)
    await user.send(embed=embed)
    await ctx.send(embed=discord.Embed(
        description=f"✅ Message sent to {user}.",
        color=discord.Color.green()
    ))

# ------------------------
# /open
# ------------------------
@bot.tree.command(name="open", description="Manually open a ModMail thread.")
@app_commands.describe(user="User to open with")
async def open_modmail(interaction: discord.Interaction, user: discord.User):
    guild = bot.get_guild(STAFF_GUILD_ID)
    category = discord.utils.get(guild.categories, id=ACTIVE_ID)
    if user.id in active_threads:
        await interaction.response.send_message("❌ User already has an open ModMail.", ephemeral=True)
        return

    channel = await guild.create_text_channel(
        name=f"modmail-{user.name}",
        category=category,
        topic=f"Manual ModMail for {user} ({user.id})"
    )
    active_threads[user.id] = channel.id
    await channel.send(embed=discord.Embed(
        title="📬 ModMail Opened",
        description=f"Opened manually for {user.mention}",
        color=discord.Color.blue()
    ))
    await interaction.response.send_message(f"✅ Opened ModMail for {user}.", ephemeral=True)

# ------------------------
# /close
# ------------------------
@bot.tree.command(name="close", description="Close this ModMail thread.")
async def close_modmail(interaction: discord.Interaction):
    guild = bot.get_guild(STAFF_GUILD_ID)
    closed_cat = discord.utils.get(guild.categories, id=CLOSED_ID)
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    channel = interaction.channel

    # Find user linked
    user_id = None
    for uid, cid in active_threads.items():
        if cid == channel.id:
            user_id = uid
            break

    if user_id:
        active_threads.pop(user_id)
        user = await bot.fetch_user(user_id)
        await user.send(embed=discord.Embed(
            title="📪 ModMail Closed",
            description=f"Closed by {interaction.user}.",
            color=discord.Color.red()
        ))

    # Move to Closed category
    await channel.edit(name=f"closed-{channel.name}", category=closed_cat)
    embed = discord.Embed(
        title="📕 Thread Closed",
        description=f"Closed by {interaction.user.mention}",
        color=discord.Color.red()
    )
    await channel.send(embed=embed)
    if log_channel:
        await log_channel.send(embed=embed)
    await interaction.response.send_message("✅ Thread closed.", ephemeral=True)

# ------------------------
# /archive
# ------------------------
@bot.tree.command(name="archive", description="Move this ModMail to Archive.")
async def archive_modmail(interaction: discord.Interaction):
    guild = bot.get_guild(STAFF_GUILD_ID)
    archive_cat = discord.utils.get(guild.categories, id=ARCHIVE_ID)
    await interaction.channel.edit(category=archive_cat)
    await interaction.response.send_message("✅ Thread archived.", ephemeral=True)

# ------------------------
# /lock
# ------------------------
@bot.tree.command(name="lock", description="Lock this ModMail thread.")
async def lock_modmail(interaction: discord.Interaction):
    overwrites = interaction.channel.overwrites
    for role in overwrites:
        overwrites[role].send_messages = False
    await interaction.channel.edit(overwrites=overwrites)
    await interaction.response.send_message("🔒 Thread locked.", ephemeral=True)

# ------------------------
# /claim
# ------------------------
@bot.tree.command(name="claim", description="Claim this ModMail thread.")
async def claim_modmail(interaction: discord.Interaction):
    guild = bot.get_guild(STAFF_GUILD_ID)
    claimed_cat = discord.utils.get(guild.categories, id=CLAIMED_ID)
    claimed_threads[interaction.channel.id] = interaction.user.id
    await interaction.channel.edit(category=claimed_cat)
    embed = discord.Embed(
        title="👤 Thread Claimed",
        description=f"Claimed by {interaction.user.mention}",
        color=discord.Color.gold()
    )
    await interaction.channel.send(embed=embed)
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=embed)
    await interaction.response.send_message("✅ Claimed.", ephemeral=True)

# ------------------------
# /add
# ------------------------
@bot.tree.command(name="add", description="Add another user to this ModMail thread.")
@app_commands.describe(user="User to add")
async def add_user(interaction: discord.Interaction, user: discord.User):
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
    await user.send(embed=discord.Embed(
        title="👋 Added to ModMail",
        description=f"You were added by {interaction.user.mention}.",
        color=discord.Color.yellow()
    ))
    await interaction.response.send_message(f"✅ Added {user.mention}.", ephemeral=True)

# ------------------------
# /userinfo
# ------------------------
@bot.tree.command(name="userinfo", description="See shared servers and roles for a user.")
@app_commands.describe(user="User to inspect")
async def userinfo(interaction: discord.Interaction, user: discord.User):
    shared = [g.name for g in bot.guilds if g.get_member(user.id)]
    embed = discord.Embed(title=f"ℹ️ Info for {user}", color=discord.Color.blurple())
    embed.add_field(name="Shared Servers", value="\n".join(shared) or "None")

    member = interaction.guild.get_member(user.id)
    if member:
        roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed.add_field(name="Roles", value=", ".join(roles) or "No roles")
    else:
        embed.add_field(name="Roles", value="Not in this server")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------
# Run bot
# ------------------------
bot.run(TOKEN)
