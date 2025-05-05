import logging
import discord
import requests
import os
import sqlite3

from logging.handlers import RotatingFileHandler
from discord.ext import tasks, commands
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- bot config ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PTCG_URLS = ["https://www.pokebeach.com/"]
POCKET_URLS = ["https://www.pokemon-zone.com/articles/", "https://www.pokemon-zone.com/events/"]
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    # cursor.execute('''CREATE TABLE IF NOT EXISTS word_check (
    #                     server_id TEXT PRIMARY KEY,
    #                     role_id TEXT,
    #                     enabled INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

setup_database()

# --- SQLite Functions ---
# SQLite - SAVES articles to prevent future repeating articles
def save_posted_article(link):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO posted_articles (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

# SQLite - LOADS previously posted articles to avoid repeats
def load_posted_articles():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM posted_articles")
    links = {row[0] for row in cursor.fetchall()}
    conn.close()
    return links

# SQLite - SAVES the posting channel for PTCG articles
def save_ptcg_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ptcg_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                   (server_id, channel_id))
    conn.commit()
    conn.close()

# SQLite - GETS the posting channel for PTCG articles
def get_ptcg_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM ptcg_channels WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# SQLite - SAVES the ping role for PTCG articles
def save_ptcg_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ptcg_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                   (server_id, role_id))
    conn.commit()
    conn.close()

# SQLite - GETS the ping role for PTCG articles
def get_ptcg_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id FROM ptcg_roles WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# SQLite - SAVES the posting channel for Pocket articles
def save_pocket_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pocket_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                   (server_id, channel_id))
    conn.commit()
    conn.close()

# SQLite - GETS the posting channel for Pocket articles
def get_pocket_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM pocket_channels WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# SQLite - SAVES the ping role for Pocket articles
def save_pocket_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pocket_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                   (server_id, role_id))
    conn.commit()
    conn.close()

# SQLite - GETS the ping role for Pocket articles
def get_pocket_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id FROM pocket_roles WHERE server_id = ?", (server_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# # SQLite - toggles on/off the function for word checking
# def toggle_word_check(guild_id):
#     conn = sqlite3.connect(DB_FILE)
#     c = conn.cursor()
#     current = is_word_check_enabled(guild_id)
#     if current:
#         c.execute("UPDATE word_check SET enabled = 0 WHERE guild_id = ?", (guild_id,))
#     else:
#         c.execute("INSERT OR REPLACE INTO word_check (guild_id, enabled) VALUES (?, ?)", (guild_id, 1))
#     conn.commit()
#     conn.close()
#     return not current

# # SQLite - checks if the word checking function is turned on or off for each server
# def is_word_check_enabled(guild_id):
#     conn = sqlite3.connect(DB_FILE)
#     c = conn.cursor()
#     c.execute("SELECT enabled FROM word_check WHERE guild_id = ?", (guild_id,))
#     row = c.fetchone()
#     conn.close()
#     return row[0] == 1 if row else False

# --- Discord Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
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
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Error fetching the webpage: {url}. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Request error while fetching {url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')

    if 'articles' in url:
        title_tag_name = 'h3'
        article_class = 'article-preview'
    else:
        title_tag_name = 'h2'
        article_class = 'featured-article-preview'

    articles = soup.find_all('article', class_=article_class)
    fetched_articles = []

    for article in articles:
        title_tag = article.find(title_tag_name)
        link_tag = article.find('a')
        image_tag = article.find('img')

        if title_tag and link_tag and image_tag:
            title = title_tag.text.strip()
            link = link_tag['href']
            full_link = f"https://www.pokemon-zone.com{link}" if link.startswith("/") else link
            image_url = image_tag['src']
            fetched_articles.append((title, full_link, image_url))

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
    first_paragraph = soup.find('p')
    return first_paragraph.text.strip() if first_paragraph else ""

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
    logger.info("Checking for new articles...")
    posted_links = load_posted_articles()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # PTCG
    cursor.execute("SELECT server_id, channel_id FROM ptcg_channels")
    ptcg_channels = cursor.fetchall()

    ptcg_articles = []
    for url in PTCG_URLS:
        all_articles = fetch_ptcg_articles(url)

        for title, link, image_url in all_articles:
            if link not in posted_links:
                ptcg_articles.append((title, link, image_url))

    # Post to all configured channels
    for server_id, channel_id in ptcg_channels:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Channel {channel_id} not found for server {server_id}.")
            continue

        if ptcg_articles:
            role_id = get_ptcg_role(server_id)
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, ptcg_articles, role_mention=role_mention, paragraph_fetcher=fetch_ptcg_first_paragraph)
    
    posted_links.update({link for _, link, _ in ptcg_articles})
    for link in {link for _, link, _ in ptcg_articles}:
        save_posted_article(link)
    
    # POCKET
    cursor.execute("SELECT server_id, channel_id FROM pocket_channels")
    pocket_channels = cursor.fetchall()

    pocket_articles = []
    for url in POCKET_URLS:
        all_articles = fetch_pocket_articles(url)
        for title, link, image_url in all_articles:
            if link not in posted_links:
                pocket_articles.append((title, link, image_url))

    for server_id, channel_id in pocket_channels:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Pocket channel {channel_id} not found for server {server_id}.")
            continue
        if pocket_articles:
            role_id = get_pocket_role(server_id) 
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, pocket_articles, role_mention=role_mention, paragraph_fetcher=fetch_pocket_first_paragraph)

    posted_links.update({link for _, link, _ in pocket_articles})
    for link in {link for _, link, _ in pocket_articles}:
        save_posted_article(link)
        posted_links.add(link)

    conn.close()

# --- Slash Commands ---
# /setptcg
@bot.tree.command(name="setptcg", description="Set the channel and role for PTCG updates.")
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
        f"✅ Updates will be posted in {channel.mention} and the role {role.mention} will be pinged.",
        ephemeral=True
    )

# /setpocket
@bot.tree.command(name="setpocket", description="Set the channel and role for Pokémon Pocket updates.")
async def setpocket(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    if not interaction.user.guild_permissions.manage_channels or not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need `Manage Channels` and `Manage Roles` permissions.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    save_pocket_channel(server_id, str(channel.id))
    save_pocket_role(server_id, str(role.id))

    await interaction.response.send_message(
        f"✅ Pocket updates will be posted in {channel.mention} and ping {role.mention}.",
        ephemeral=True
    )

# /update
@bot.tree.command(name="update", description="Check for new PTCG updates.")
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
        await post_articles(channel, ptcg_articles)
        await interaction.followup.send(f"Posted {len(ptcg_articles)} articles. ✅", ephemeral=True)
    else:
        await interaction.followup.send("No new articles found. ✅", ephemeral=True)

# /trading (similar to /togglewordcheck but this is manual and can be ignored if unused)
@bot.tree.command(name="trading", description="Tell users how to access the trading channels.")
async def trading(interaction: discord.Interaction):
        await interaction.response.send_message(
            "Please read the post titled **READ ME** at the top of the trading channel for more information on how to trade. 🏛️"
        )

# # /togglewordcheck
# @bot.tree.command(name="togglewordcheck", description="Toggle on/off the word checking functionality.")
# async def togglewordcheck(interaction: discord.Interaction):
#     if not interaction.user.guild_permissions.administrator:
#         await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
#         return

#     await interaction.response.defer()

#     new_state = toggle_word_check(interaction.guild.id)
#     status = "enabled" if new_state else "disabled"
#     await interaction.followup.send(f"Word check has been {status}.")


# --- Events ---
# log in event
@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"Logged in as {bot.user}")
    if not check_and_post_articles.is_running():
        check_and_post_articles.start()

# new server welcome event
@bot.event
async def on_guild_join(guild):
    try:
        owner = guild.owner

        if owner:
            message = (
                f"Hey {owner.name}! Here are some tips to get me set up in your server.\n\n"
                "**/setptcg <channel> <role>** - Set the channel and role for **PTCG** news updates.\n"
                "**/setpocket <channel> <role>** - Set the channel and role for **PTCG Pocket** news updates.\n\n"
                "If you need help, please create a ticket in the Pokémon TCG/Live/Pocket Community."
            )
            await owner.send(message)
            logger.info(f"Sent welcome message to the owner of {guild.name}.")
        else:
            logger.warning(f"Could not find the owner for the guild {guild.name}.")
    except Exception as e:
        logger.error(f"Failed to send a welcome message for guild {guild.name}: {e}")

# # "pocket" & "trading" word check event
# @bot.event
# async def on_message(message):
#     if message.author.bot:
#         return  # ignore messages from other bots

#     if is_word_check_enabled(message.guild.id):
#         lower_msg = message.content.lower()
#         if "pocket" in lower_msg and "trading" in lower_msg:
#             await message.channel.send(
#                 "Please read the post titled **READ ME** at the top of the trading channel for more information on how to trade. 🏛️"
#             )

#     await bot.process_commands(message)


bot.run(TOKEN)
