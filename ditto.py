# im gonna put everything in one file because its easier for me to dev on one device and just copy everything into my raspberry pi thats hosting the bot

import logging
import discord
import requests
import os
import sqlite3
import re

from logging.handlers import RotatingFileHandler
from discord.ext import tasks, commands
from discord.ext.commands import cooldown, BucketType
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- Bot config ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PTCG_URLS = ["https://www.pokebeach.com/"]
POCKET_URLS = ["https://www.pokemon-zone.com/"]
DB_FILE = "bot_data.db"

# --- Logging setup ---
log_file = "bot_activity.log"
logger = logging.getLogger("dittologger")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# --- SQLite Setup ---
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Posted articles
    cursor.execute('''CREATE TABLE IF NOT EXISTS posted_articles (
                        link TEXT PRIMARY KEY)''')

    # PTCG channels & roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    # Pocket channels & roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    # Regex patterns
    cursor.execute('''CREATE TABLE IF NOT EXISTS regex_patterns (
                        server_id TEXT PRIMARY KEY,
                        pattern TEXT)''')
    
    # Regex-ignored channels
    cursor.execute('''CREATE TABLE IF NOT EXISTS regex_ignored_channels (
                    server_id TEXT,
                    channel_id TEXT,
                    PRIMARY KEY (server_id, channel_id))''')
    
    conn.commit()
    conn.close()

    logger.info(f"Database successfully set up!")

setup_database()

# --- SQLite Functions ---
# SQLite - SAVES articles to prevent future repeating articles
def save_posted_article(link):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO posted_articles (link) VALUES (?)", (link,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save article: {e}")
    finally:
        conn.close()

# SQLite - LOADS previously posted articles to avoid repeats
def load_posted_articles():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM posted_articles")
        links = {row[0] for row in cursor.fetchall()}
        return links
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to load articles: {e}")
        return set()
    finally:
        conn.close()

# SQLite - SAVES the posting channel for PTCG articles
def save_ptcg_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ptcg_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                    (server_id, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save ptcg channel: {e}")
    finally:
        conn.close()

# SQLite - GETS the posting channel for PTCG articles
def get_ptcg_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM ptcg_channels WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get ptcg channel: {e}")
        return None
    finally:
        conn.close()

# SQLite - SAVES the ping role for PTCG articles
def save_ptcg_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ptcg_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                    (server_id, role_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save ptcg role: {e}")
    finally:
        conn.close()

# SQLite - GETS the ping role for PTCG articles
def get_ptcg_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM ptcg_roles WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get ptcg role: {e}")
        return None
    finally:
        conn.close()

# SQLite - SAVES the posting channel for Pocket articles
def save_pocket_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pocket_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                    (server_id, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save pocket channel: {e}")
    finally:
        conn.close()

# SQLite - GETS the posting channel for Pocket articles
def get_pocket_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM pocket_channels WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get pocket channel: {e}")
        return None
    finally:
        conn.close()

# SQLite - SAVES the ping role for Pocket articles
def save_pocket_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pocket_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                    (server_id, role_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save pocket role: {e}")
    finally:
        conn.close()

# SQLite - GETS the ping role for Pocket articles
def get_pocket_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM pocket_roles WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get pocket role: {e}")
        return None
    finally:
        conn.close()

# SQLite - SAVES regex pattern
def save_regex_pattern(server_id, pattern):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO regex_patterns (server_id, pattern) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET pattern = excluded.pattern", 
                    (server_id, pattern))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save regex pattern: {e}")
    finally:
        conn.close()

# SQLite - GETS regex pattern
def get_regex_pattern(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pattern FROM regex_patterns WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get regex pattern: {e}")
        return None
    finally:
        conn.close()

# SQLite - REMOVES regex pattern
def remove_regex_pattern(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM regex_patterns WHERE server_id = ?", (server_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to remove regex pattern: {e}")
    finally:
        conn.close()

# SQLite - SAVES regex ignored channel
def save_regex_ignored_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO regex_ignored_channels (server_id, channel_id) VALUES (?, ?)",
            (server_id, channel_id),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save regex ignored channel: {e}")
    finally:
        conn.close()

# SQLite - REMOVES regex ignored channel
def remove_regex_ignored_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM regex_ignored_channels WHERE server_id = ? AND channel_id = ?",
            (server_id, channel_id),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to remove regex ignored channel: {e}")
    finally:
        conn.close()

# SQLite - GETS regex ignored channel
def get_regex_ignored_channels(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT channel_id FROM regex_ignored_channels WHERE server_id = ?", (server_id,)
        )
        ignored = {row[0] for row in cursor.fetchall()}
        return ignored
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get regex ignored channels: {e}")
        return set()
    finally:
        conn.close()

# --- Discord Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Fetch Articles ---
# PTCG
def fetch_ptcg_articles(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Error fetching the webpage: {url}. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error while fetching {url}: {e}")
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

    logger.info(f"Fetched {len(fetched_articles)} articles from {url}.")
    return fetched_articles

def fetch_ptcg_first_paragraph(article_url):
    try:
        response = requests.get(article_url)
        if response.status_code != 200:
            logger.error(f"Error fetching the article {article_url}. Status code: {response.status_code}")
            return ""
    except requests.RequestException as e:
        logger.error(f"Request error while fetching {article_url}: {e}")
        return ""
    
    soup = BeautifulSoup(response.content, 'html.parser')
    first_article = soup.find('article')
    if not first_article:
        logger.warning(f"No <article> tag found in the article {article_url}.")
        return "No content available."

    nested_div = first_article.find('div')
    if nested_div:
        nested_div = nested_div.find('div') 
        if nested_div:
            nested_div = nested_div.find('div')  
            if nested_div:
                first_paragraph = nested_div.find('p')  
                if first_paragraph:
                    return first_paragraph.text.strip()
    
    logger.warning(f"No <p> tag found in the article {article_url}.")
    return "No content available."

# POCKET
def fetch_pocket_articles(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Error fetching Pocket articles: Status {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error fetching Pocket articles: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    fetched_articles = []
    
    for article in soup.select("article[class*='preview']"):
        title_tag = article.select_one("h2[class*='title']")
        link_tag = article.select_one("a[class*='poster']")
        image_tag = article.select_one("img")

        if title_tag and link_tag and image_tag:
            title = title_tag.text.strip()
            
            link = link_tag.get('href')
            if not link:
                continue 
            full_link = f"https://www.pokemon-zone.com{link}" if link.startswith('/') else link

            image_src = image_tag.get('src')
            if not image_src:
                continue 
            full_image_url = image_src
            if image_src.startswith('/'):
                full_image_url = f"https://www.pokemon-zone.com{image_src}"
            
            fetched_articles.append((title, full_link, full_image_url))

    logger.info(f"Fetched {len(fetched_articles)} articles from {url}.")
    return fetched_articles

def fetch_pocket_first_paragraph(article_url):
    try:
        response = requests.get(article_url)
        if response.status_code != 200:
            logger.error(f"Error fetching the article {article_url}. Status code: {response.status_code}")
            return ""
    except requests.RequestException as e:
        logger.error(f"Request error while fetching {article_url}: {e}")
        return ""

    soup = BeautifulSoup(response.content, 'html.parser')
    first_article = soup.find('article')
    if not first_article:
        logger.warning(f"No <article> tag found in the article {article_url}.")
        return "No content available."

    first_paragraph = first_article.find('p')  
    if first_paragraph:
        return first_paragraph.text.strip()
    
    logger.warning(f"No <p> tag found in the article {article_url}.")
    return "No content available."

# --- Post Articles ---
async def post_articles(channel, articles, role_mention=None, paragraph_fetcher=None):
    for title, link, image_url in articles:
        first_paragraph = paragraph_fetcher(link) if paragraph_fetcher else ""
        description = f"{first_paragraph}\n\nRead more at {link}"

        embed = discord.Embed(title=title, url=link, description=description)
        embed.set_image(url=image_url)

        try:
            if role_mention:
                await channel.send(
                    content=role_mention,
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )
            await channel.send(embed=embed)
            save_posted_article(link)
            logger.info(f"Posted article: {title} - {link}")
        except Exception as e:
            logger.error(f"Failed to send message in channel {channel.id}: {e}")

# --- Background Task ---
@tasks.loop(hours=1)
async def check_and_post_articles():
    logger.info("Running hourly check for new articles...")
    posted_links = load_posted_articles()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # --- PTCG ---
    cursor.execute("SELECT server_id, channel_id FROM ptcg_channels")
    ptcg_channels = cursor.fetchall()

    new_ptcg_articles = []
    for url in PTCG_URLS:
        all_articles = fetch_ptcg_articles(url)
        for article_data in all_articles:
            if article_data[1] not in posted_links:
                new_ptcg_articles.append(article_data)
                posted_links.add(article_data[1])

    if new_ptcg_articles and ptcg_channels:
        for server_id, channel_id in ptcg_channels:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"Channel {channel_id} not found for server {server_id}.")
                continue
            
            role_id = get_ptcg_role(server_id)
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, new_ptcg_articles, role_mention=role_mention, paragraph_fetcher=fetch_ptcg_first_paragraph)
    
    # --- POCKET ---
    cursor.execute("SELECT server_id, channel_id FROM pocket_channels")
    pocket_channels = cursor.fetchall()

    new_pocket_articles = []
    for url in POCKET_URLS:
        all_articles = fetch_pocket_articles(url)
        for article_data in all_articles:
            if article_data[1] not in posted_links:
                new_pocket_articles.append(article_data)
                posted_links.add(article_data[1])

    if new_pocket_articles and pocket_channels:
        for server_id, channel_id in pocket_channels:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"Pocket channel {channel_id} not found for server {server_id}.")
                continue
            
            role_id = get_pocket_role(server_id) 
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, new_pocket_articles, role_mention=role_mention, paragraph_fetcher=fetch_pocket_first_paragraph)

    conn.close()
    logger.info("Finished hourly check.")

# --- Slash Commands ---
# /setptcg
@bot.tree.command(name="setptcg", description="Set the channel and role for PTCG updates")
async def setptcg(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    if not interaction.user.guild_permissions.manage_channels or not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "You need both `Manage Channels` and `Manage Roles` permissions to use this command.", 
            ephemeral=True
        )
        return

    server_id = str(interaction.guild_id)
    save_ptcg_channel(server_id, str(channel.id))
    save_ptcg_role(server_id, str(role.id))

    await interaction.response.send_message(
        f"✅ Updates will be posted in {channel.mention} and the role {role.mention} will be pinged."
    )
    logger.info(f"/setptcg command run on server {server_id}. Channel: {channel.id} | Role: {role.id}.")

# /setpocket
@bot.tree.command(name="setpocket", description="Set the channel and role for Pokémon Pocket updates")
async def setpocket(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    if not interaction.user.guild_permissions.manage_channels or not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need `Manage Channels` and `Manage Roles` permissions.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    save_pocket_channel(server_id, str(channel.id))
    save_pocket_role(server_id, str(role.id))

    await interaction.response.send_message(
        f"✅ Pocket updates will be posted in {channel.mention} and ping {role.mention}."
    )
    logger.info(f"/setpocket command run on server {server_id}. | Channel: {channel.id} - Role: {role.id}.")

# /update
@bot.tree.command(name="update", description="Check for news updates")
@cooldown(1, 60, BucketType.user)   # 1 use per 60 seconds
async def update(interaction: discord.Interaction):
    await interaction.response.send_message("Checking for new articles... ⏳", ephemeral=True)

    server_id = str(interaction.guild_id)
    channel_id = get_ptcg_channel(server_id)
    if not channel_id:
        await interaction.followup.send("No channel set. Use `/setptcg` first.", ephemeral=True)
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await interaction.followup.send("Invalid channel. Reset it with `/setptcg`.", ephemeral=True)
        return

    ptcg_articles = [a for url in PTCG_URLS for a in fetch_ptcg_articles(url) if a[1] not in load_posted_articles()]
    
    if ptcg_articles:
        role_id = get_ptcg_role(server_id)
        role_mention = f"<@&{role_id}>" if role_id else None
        await post_articles(channel, ptcg_articles, role_mention=role_mention, paragraph_fetcher=fetch_ptcg_first_paragraph)
        await interaction.followup.send(f"Posted {len(ptcg_articles)} articles. ✅", ephemeral=True)
    else:
        await interaction.followup.send("No new articles found. ✅", ephemeral=True)

    logger.info(f"/update command run on server {server_id}")

# /trading (manual warning message)
@bot.tree.command(name="trading", description="Manual command to tell users how to access the trading channels")
@cooldown(1, 60, BucketType.user)   # 1 use per 60 seconds
async def trading(interaction: discord.Interaction):
    server_id = str(interaction.guild_id)
    await interaction.response.send_message(
        "Please read the post titled **READ ME** at the top of <#1334205216320655483> for more information on how to trade. 🏛️"
    )

    logger.info(f"/trading command run on server {server_id}.")

# /setregex
@bot.tree.command(name="setregex", description="Set a regex pattern for word checking")
async def setregex(interaction: discord.Interaction, pattern: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return
    
    try:
        re.compile(pattern) # validate regex pattern
    except re.error:
        await interaction.response.send_message("Invalid regex pattern.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    save_regex_pattern(server_id, pattern)

    await interaction.response.send_message(f"✅ Regex pattern set to: `{pattern}`")

    logger.info(f"/setregex command run on server {server_id}. | Pattern: {pattern}.")

# /removeregex
@bot.tree.command(name="removeregex", description="Remove the regex pattern for word checking")
async def removeregex(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    remove_regex_pattern(server_id)

    await interaction.response.send_message("✅ Regex pattern removed.")

    logger.info(f"/removeregex command run on server {server_id}.")

# /addignoredchannel
@bot.tree.command(name="addignoredchannel", description="Add a channel to be ignored by the regex check")
async def addignoredchannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    save_regex_ignored_channel(server_id, str(channel.id))

    await interaction.response.send_message(f"✅ Channel {channel.mention} has been added to the ignored list.")

    logger.info(f"/addignoredchannel command run on server {server_id}. | Channel: {channel.mention}.")

# /removeignoredchannel
@bot.tree.command(name="removeignoredchannel", description="Remove a channel to be ignored by the regex check")
async def removeignoredchannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    remove_regex_ignored_channel(server_id, str(channel.id))

    await interaction.response.send_message(f"✅ Channel {channel.mention} has been removed from the ignored list.")

    logger.info(f"/removeignoredchannel command run on server {server_id}. | Channel: {channel.mention}.")

# /listignoredchannels
@bot.tree.command(name="listignoredchannels", description="Lists all channels ignored by the regex check")
async def listignoredchannels(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    ignored_channels = get_regex_ignored_channels(server_id)

    if ignored_channels:
        channels = [f"<#{channel_id}>" for channel_id in ignored_channels]
        await interaction.response.send_message(
            "✅ Ignored channels:\n" + "\n".join(channels)
        )
    else:
        await interaction.response.send_message("No channels are currently ignored.", ephemeral=True)

    logger.info(f"/listignoredchannels command run on server {server_id}.")

# --- Events ---
# log in event
@bot.event
async def on_ready():
    await bot.tree.sync()
    if not check_and_post_articles.is_running():
        check_and_post_articles.start()
    logger.info(f"Logged in as {bot.user}")

# new server welcome event
@bot.event
async def on_guild_join(guild):
    try:
        # read the audit log to find who added the bot
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.target.id == bot.user.id:
                inviter = entry.user
                message = (
                    f"Hey {inviter.name}! Here are some tips to get me set up in your server.\n\n"
                    "__News Updates__\n"
                    "**/setptcg <channel> <role>** - Set the channel and role for **PTCG** news updates.\n"
                    "**/setpocket <channel> <role>** - Set the channel and role for **PTCG Pocket** news updates.\n"
                    "**/update** - Check for news updates.\n\n"
                    "__Regex__\n"
                    "**/setregex <pattern>** - Set a regex pattern for word checking.\n"
                    "**/removeregex** - Remove the regex pattern.\n"
                    "**/addignoredchannel <channel>** - Add a channel to be ignored by the regex check.\n"
                    "**/removeignoredchannel <channel>** - Remove a channel to be ignored by the regex check.\n"
                    "**/listignoredchannels** - Lists all channels ignored by the regex check.\n"
                    "**/trading** - Manual command to tell users how to access the trading channels.\n\n"
                    "If you need help, please create a ticket in the Pokémon TCG/Live/Pocket Community."
                )
                await inviter.send(message)
                logger.info(f"Bot added to new server of ID {guild.id} by {inviter.name}")
                logger.info(f"Sent welcome message to {inviter.name} who added the bot to {guild.name}.")
                return
        
        # if audit log check fails just send the msg to the owner
        owner = guild.owner
        if owner:
            message = (
                f"Hey {owner.name}! Here are some tips to get me set up in your server.\n\n"
                "__News Updates__\n"
                "**/setptcg <channel> <role>** - Set the channel and role for **PTCG** news updates.\n"
                "**/setpocket <channel> <role>** - Set the channel and role for **PTCG Pocket** news updates.\n"
                "**/update** - Check for news updates.\n\n"
                "__Regex__\n"
                "**/setregex <pattern>** - Set a regex pattern for word checking.\n"
                "**/removeregex** - Remove the regex pattern.\n"
                "**/addignoredchannel <channel>** - Add a channel to be ignored by the regex check.\n"
                "**/removeignoredchannel <channel>** - Remove a channel to be ignored by the regex check.\n"
                "**/listignoredchannels** - Lists all channels ignored by the regex check.\n"
                "**/trading** - Manual command to tell users how to access the trading channels.\n\n"
                "If you need help, please create a ticket in the Pokémon TCG/Live/Pocket Community."
            )
            await owner.send(message)
            logger.info(f"Bot added to new server of ID {guild.id} - sent message to owner as fallback")
        else:
            logger.warning(f"Could not find the owner for the guild {guild.name}.")
    except Exception as e:
        logger.error(f"Failed to send a welcome message for guild {guild.name}: {e}")

# regex check event
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # ignore messages from other bots
    
    if not message.guild:
        return

    server_id = str(message.guild.id)
    ignored_channels = get_regex_ignored_channels(server_id)

    # check if the message's channel or its parent (for forum posts) is ignored
    if str(message.channel.id) in ignored_channels or (
        hasattr(message.channel, "parent") and str(message.channel.parent.id) in ignored_channels
    ):
        return

    pattern = get_regex_pattern(server_id)
    if pattern and re.search(pattern, message.content, re.IGNORECASE):
        await message.reply(
            "👋🏽 Hey! It seems like you're looking to trade cards.\n\n"
            "We already have a specific channel for trading in PTCG Pocket so please read the post titled **READ ME** at the top of <#1334205216320655483> for more information. 🏛️\n"
            "If you're unable to make a listing, please grab the *Union Room* role at <#908131369085968394>!"
        )
        logger.info(f"Regex match triggered at server {server_id}.")

    await bot.process_commands(message)


bot.run(TOKEN)
