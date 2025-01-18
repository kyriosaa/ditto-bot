import logging
from logging.handlers import RotatingFileHandler
import discord
from discord.ext import tasks, commands
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import json

# --- bot config ---
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
URLS = [
    "https://www.pokebeach.com/"
]
POSTED_ARTICLES_FILE = "posted_articles.json"
SERVER_CHANNELS_FILE = "server_channels.json"
SERVER_ROLES_FILE = "server_roles.json"

# --- logging setup ---
log_file = "bot_activity.log"
logger = logging.getLogger("ptcg-news")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=100)  # 100MB per file, 100 backups
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# --- track posted articles ---
posted_articles = set()

def load_posted_articles():
    if os.path.exists(POSTED_ARTICLES_FILE):
        try:
            with open(POSTED_ARTICLES_FILE, "r") as file:
                return set(json.load(file))
        except json.JSONDecodeError:
            logger.error("Error decoding JSON file. Starting with an empty set.")
            return set()
    return set()

def save_posted_articles():
    try:
        with open(POSTED_ARTICLES_FILE, "w") as file:
            json.dump(list(posted_articles), file)
    except Exception as e:
        logger.error(f"Error saving posted articles: {e}")

# --- track server channels ---
server_channels = {}

def load_server_channels():
    if os.path.exists(SERVER_CHANNELS_FILE):
        try:
            with open(SERVER_CHANNELS_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.error("Error decoding server channels file. Starting with an empty dictionary.")
            return {}
    return {}

def save_server_channels(data):
    try:
        with open(SERVER_CHANNELS_FILE, "w") as file:
            json.dump(data, file)
    except Exception as e:
        logger.error(f"Error saving server channels: {e}")

# --- track server roles ---
server_roles = {}

def load_server_roles():
    if os.path.exists(SERVER_ROLES_FILE):
        try:
            with open(SERVER_ROLES_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.error("Error decoding server roles file. Starting with an empty dictionary.")
            return {}
    return {}

def save_server_roles(data):
    try:
        with open(SERVER_ROLES_FILE, "w") as file:
            json.dump(data, file)
    except Exception as e:
        logger.error(f"Error saving server roles: {e}")

# --- Discord intents setup ---
intents = discord.Intents.default()
intents.messages = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- fetch articles ---
def fetch_articles(url):
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

def fetch_first_paragraph(article_url):
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

# --- post articles ---
async def post_articles(channel, articles):
    server_id = str(channel.guild.id)
    role_id = server_roles.get(server_id)

    role_mention = f"<@&{role_id}>" if role_id else None

    for title, link, image_url in articles:
        first_paragraph = fetch_first_paragraph(link)
        description = f"{first_paragraph}\n\nRead more at {link}"

        embed = discord.Embed(title=title, url=link, description=description)
        embed.set_image(url=image_url)

        try:
            if role_mention: 
                await channel.send(content=role_mention)
            
            await channel.send(embed=embed)
            logger.info(f"Posted article: {title} - {link}")
        except Exception as e:
            logger.error(f"Failed to send message in channel {channel.id}: {e}")




# --- background check ---
@tasks.loop(hours=1)
async def check_and_post_articles():
    logger.info("Checking for new articles...")

    for server_id, channel_id in server_channels.items():
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.error(f"Channel {channel_id} not found for server {server_id}.")
            continue

        new_articles = []
        for url in URLS:
            all_articles = fetch_articles(url)

            for title, link, image_url in all_articles:
                if link not in posted_articles:
                    new_articles.append((title, link, image_url))
                    posted_articles.add(link)

        if new_articles:
            logger.info(f"Found {len(new_articles)} new articles for server {server_id}.")
            try:
                await post_articles(channel, new_articles)
            except Exception as e:
                logger.error(f"Error posting articles to channel {channel_id}: {e}")

    save_posted_articles()


# --- /setchannel ---
@bot.tree.command(name="setchannel", description="Set the channel for article updates.")
async def setchannel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message(
            "You need the `Manage Channels` permission to use this command.", ephemeral=True
        )
        return

    server_id = str(interaction.guild_id)
    channel_id = str(interaction.channel_id)

    server_channels[server_id] = channel_id
    save_server_channels(server_channels)

    await interaction.response.send_message(
        f"Updates will now be posted in this channel: {interaction.channel.mention} ✅", ephemeral=True
    )
    logger.info(f"Set posting channel for server {server_id} to channel {channel_id}")

# --- /setrole ---
@bot.tree.command(name="setrole", description="Set the role to ping for article updates.")
async def setrole(interaction: discord.Interaction, role: discord.Role):
    try:
        logger.info(f"Setrole command triggered by {interaction.user} in server {interaction.guild_id} with role {role.id}")

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "You need the `Manage Roles` permission to use this command.", ephemeral=True
            )
            return

        server_id = str(interaction.guild_id)
        server_roles[server_id] = str(role.id)
        save_server_roles(server_roles)

        await interaction.response.send_message(
            f"The role {role.mention} will now be pinged for article updates. ✅", ephemeral=True
        )

        logger.info(f"Set role for server {server_id} to role {role.id} ({role.name}).")
    except Exception as e:
        logger.error(f"Error in /setrole command: {e}")
        await interaction.response.send_message(
            "An error occurred while setting the role. Please try again later.", ephemeral=True
        )




# --- /ptcgnews ---
@bot.tree.command(name="ptcgnews", description="Check for updates on the Pokemon Trading Card Game.")
async def ptcgnews(interaction: discord.Interaction):
    logger.info("Slash command /ptcgnews triggered.")
    await interaction.response.send_message("Checking for new articles... ⏳", ephemeral=True)

    server_id = str(interaction.guild_id)
    channel_id = server_channels.get(server_id)
    if not channel_id:
        await interaction.followup.send("No channel has been set for this server. Use `/setchannel` first.", ephemeral=True)
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await interaction.followup.send("The set channel could not be found. Please set it again using `/setchannel`.", ephemeral=True)
        return

    new_articles = []
    for url in URLS:
        all_articles = fetch_articles(url)

        for title, link, image_url in all_articles:
            if link not in posted_articles:
                new_articles.append((title, link, image_url))
                posted_articles.add(link)

    if new_articles:
        await post_articles(channel, new_articles)
        save_posted_articles()
        await interaction.followup.send(f"Posted {len(new_articles)} new article(s). ✅", ephemeral=True)
    else:
        await interaction.followup.send("No new articles found. ✅", ephemeral=True)

# --- bot ready event ---
@bot.event
async def on_ready():
    global posted_articles, server_channels
    posted_articles = load_posted_articles()
    server_channels = load_server_channels()
    server_roles = load_server_roles()

    try:
        await bot.tree.sync()
        logger.info("Slash commands synced.")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")

    logger.info(f"Logged in as {bot.user}")
    check_and_post_articles.start()

bot.run(TOKEN)
