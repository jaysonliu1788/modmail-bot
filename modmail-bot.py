import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os

# ------------------------
# Load environment variables
# ------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_GUILD_ID = int(os.getenv("STAFF_GUILD_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
MODMAIL_CATEGORY_ID = int(os.getenv("MODMAIL_CATEGORY_ID"))
ARCHIVE_CATEGORY_ID = int(os.getenv("ARCHIVE_CATEGORY_ID"))
PREFIX = os.getenv("PREFIX", "?")

# ------------------------
# Setup bot
# ------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

active_threads = {}  # user_id : channel_id
claimed_threads = {} # channel_id : staff_id

# ------------------------
# On Ready
# ------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()
    print("✅ Slash commands synced")

# ------------------------
# Handle DMs
# ------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Handle DMs
    if isinstance(message.channel, discord.DMChannel):
        guild = bot.get_guild(STAFF_GUILD_ID)
        if guild is None:
            print("❌ Error: Staff guild not found.")
            return

        category = discord.utils.get(guild.categories, id=MODMAIL_CATEGORY_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)

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

            embed = discord.Embed(
                title="📬 New ModMail Opened",
                description=f"**User:** {message.author} ({message.author.id})",
                color=discord.Color.blue()
            )
            await channel.send(embed=embed)
            if log_channel:
                await log_channel.send(embed=embed)
            await message.author.send(embed=discord.Embed(
                title="ModMail Opened",
                description="Your message has been sent to staff. You can reply here to continue.",
                color=discord.Color.green()
            ))

        # Forward message to staff
        guild_channel = guild.get_channel(active_threads[message.author.id])
        if guild_channel:
            embed = discord.Embed(description=message.content, color=discord.Color.blurple())
            embed.set_author(name=message.author, icon_url=message.author.display_avatar)
            await guild_channel.send(embed=embed)

    await bot.process_commands(message)

# ------------------------
# Staff reply (prefix)
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
@bot.tree.command(name="open", description="Manually open a ModMail thread with a user.")
@app_commands.describe(user="User to open ModMail with")
async def open_modmail(interaction: discord.Interaction, user: discord.User):
    guild = bot.get_guild(STAFF_GUILD_ID)
    category = discord.utils.get(guild.categories, id=MODMAIL_CATEGORY_ID)
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
@bot.tree.command(name="close", description="Close the current ModMail thread.")
async def close_modmail(interaction: discord.Interaction):
    channel = interaction.channel
    if channel.category_id != MODMAIL_CATEGORY_ID:
        await interaction.response.send_message("❌ This is not a ModMail thread.", ephemeral=True)
        return

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

    await channel.edit(name=f"closed-{channel.name}", category=None)
    await interaction.response.send_message("✅ Thread closed.", ephemeral=True)

# ------------------------
# /archive
# ------------------------
@bot.tree.command(name="archive", description="Archive the current ModMail thread.")
async def archive_modmail(interaction: discord.Interaction):
    guild = bot.get_guild(STAFF_GUILD_ID)
    category = discord.utils.get(guild.categories, id=ARCHIVE_CATEGORY_ID)
    await interaction.channel.edit(category=category)
    await interaction.response.send_message("✅ Thread archived.", ephemeral=True)

# ------------------------
# /lock
# ------------------------
@bot.tree.command(name="lock", description="Lock the current ModMail thread.")
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
    claimed_threads[interaction.channel.id] = interaction.user.id
    await interaction.response.send_message(f"✅ Claimed by {interaction.user.mention}", ephemeral=False)

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
    await interaction.response.send_message(f"✅ Added {user.mention} to thread.", ephemeral=True)

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
