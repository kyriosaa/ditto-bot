import logging
from logging.handlers import RotatingFileHandler
import discord
from discord.ext import tasks, commands
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import sqlite3

# --- bot config ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
URLS = ["https://www.pokebeach.com/"]
DB_FILE = "bot_data.db"

# --- logging setup ---
log_file = "bot_activity.log"
logger = logging.getLogger("ptcg-news")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# --- SQLite Setup ---
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS posted_articles (
                        link TEXT PRIMARY KEY)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS server_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS server_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    conn.commit()
    conn.close()

setup_database()

# --- SQLite Functions ---
def save_posted_article(link):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO posted_articles (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def load_posted_articles():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM posted_articles")
    links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return links

def save_server_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO server_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                   (server_id, channel_id))
    conn.commit()
    conn.close()

def get_server_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM server_channels WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_server_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO server_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                   (server_id, role_id))
    conn.commit()
    conn.close()

def get_server_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id FROM server_roles WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# --- Discord Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fetch Articles ---
def fetch_articles(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Error fetching {url}: {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    articles = soup.find_all('article', class_=lambda value: value and "block" in value)
    fetched_articles = []

    for article in articles:
        title_tag = article.find('h2')
        link_tag = article.find('a')
        image_tag = article.find('img')

        if title_tag and link_tag and image_tag:
            title = title_tag.text.strip()
            link = link_tag['href']
            full_link = f"https://www.pokebeach.com{link}" if link.startswith("/") else link
            image_url = image_tag['src']
            fetched_articles.append((title, full_link, image_url))

    return fetched_articles

# --- Post Articles ---
async def post_articles(channel, articles):
    server_id = str(channel.guild.id)
    role_id = get_server_role(server_id)

    role_mention = f"<@&{role_id}>" if role_id else None

    for title, link, image_url in articles:
        embed = discord.Embed(title=title, url=link, description=f"Read more at {link}")
        embed.set_image(url=image_url)

        try:
            if role_mention:
                await channel.send(content=role_mention, allowed_mentions=discord.AllowedMentions(roles=True))
            
            await channel.send(embed=embed)
            save_posted_article(link)  # Save posted article
        except Exception as e:
            logger.error(f"Failed to send message in {channel.id}: {e}")

# --- Background Task ---
@tasks.loop(hours=1)
async def check_and_post_articles():
    logger.info("Checking for new articles...")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT server_id, channel_id FROM server_channels")
    server_channels = cursor.fetchall()
    conn.close()

    for server_id, channel_id in server_channels:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Channel {channel_id} not found for server {server_id}.")
            continue

        new_articles = []
        for url in URLS:
            all_articles = fetch_articles(url)

            for title, link, image_url in all_articles:
                if link not in load_posted_articles():
                    new_articles.append((title, link, image_url))

        if new_articles:
            await post_articles(channel, new_articles)

# --- Slash Commands ---
@bot.tree.command(name="setchannel", description="Set the channel for article updates.")
async def setchannel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("You need `Manage Channels` permission.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    save_server_channel(server_id, channel_id)
    await interaction.response.send_message(f"Updates will be posted in {interaction.channel.mention}. ✅", ephemeral=True)

@bot.tree.command(name="setrole", description="Set the role to ping for article updates.")
async def setrole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need `Manage Roles` permission.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    save_server_role(server_id, str(role.id))

    await interaction.response.send_message(f"The role {role.mention} will be pinged for updates. ✅", ephemeral=True)

@bot.tree.command(name="ptcgnews", description="Check for new PTCG updates.")
async def ptcgnews(interaction: discord.Interaction):
    await interaction.response.send_message("Checking for new articles... ⏳", ephemeral=True)

    server_id = str(interaction.guild_id)
    channel_id = get_server_channel(server_id)
    if not channel_id:
        await interaction.followup.send("No channel set. Use `/setchannel` first.", ephemeral=True)
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await interaction.followup.send("Invalid channel. Reset it with `/setchannel`.", ephemeral=True)
        return

    new_articles = [a for url in URLS for a in fetch_articles(url) if a[1] not in load_posted_articles()]
    
    if new_articles:
        await post_articles(channel, new_articles)
        await interaction.followup.send(f"Posted {len(new_articles)} articles. ✅", ephemeral=True)
    else:
        await interaction.followup.send("No new articles found. ✅", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"Logged in as {bot.user}")
    check_and_post_articles.start()

bot.run(TOKEN)
