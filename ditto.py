import discord
import io
import os
import re
import aiohttp
import asyncio
import logging
import cloudscraper
import database
import xml.etree.ElementTree as ET

from logging.handlers import RotatingFileHandler
from discord.ext import tasks, commands
from discord.ext.commands import cooldown, BucketType
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PTCG_URL = "https://www.pokebeach.com/"
POCKET_URL = "https://www.pokemon-zone.com/"

log_file = "bot_activity.log"
logger = logging.getLogger("dittologger")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

database.setup_database()

# discord setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# fetch PTCG articles
async def fetch_ptcg_articles(ptcg_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }

    def _sync_get(url):
        sc = cloudscraper.create_scraper()
        r = sc.get(url, headers=headers, timeout=15)
        return r.status_code, r.text

    try:
        status, body = await asyncio.to_thread(_sync_get, ptcg_url)
        if status != 200:
            logger.error(f"Error fetching the webpage: {ptcg_url}. Status code: {status}")
            return []
    except Exception as e:
        logger.error(f"Request error while fetching {ptcg_url}: {e}")
        return []

    soup = BeautifulSoup(body, 'html.parser')

    articles = soup.find_all('article')
    fetched_articles = []
    for article in articles:
        title_tag = article.find('h2')
        link_tag = article.find('a')
        image_tag = article.find('img')

        if title_tag and link_tag:
            title = title_tag.text.strip()
            link = link_tag.get('href')
            if not link:
                continue
            
            image_url = ""
            if image_tag:
                image_url = image_tag.get('src') or ""
            
            fetched_articles.append((title, link, image_url))

    logger.info(f"Fetched {len(fetched_articles)} articles from {ptcg_url}.")
    return fetched_articles

async def fetch_first_paragraph(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }

    def _sync_get(url):
        sc = cloudscraper.create_scraper()
        r = sc.get(url, headers=headers, timeout=15)
        return r.status_code, r.text

    try:
        status, body = await asyncio.to_thread(_sync_get, url)
        if status != 200:
            logger.error(f"Error fetching the webpage: {url}. Status code: {status}")
            return ""
    except Exception as e:
        logger.error(f"Request error while fetching {url}: {e}")
        return ""
    
    soup = BeautifulSoup(body, 'html.parser')
    
    # 1 // look for <p> inside <article>
    article_body = soup.find('article')
    if article_body:
        p = article_body.find('p')
        if p and p.text.strip():
            return p.text.strip()

    # 2 // look for <p> inside common content divs
    for class_name in ['media-block__primary', 'entry-content', 'post-content', 'content']:
        content_div = soup.find('div', class_=class_name)
        if content_div:
            p = content_div.find('p')
            if p and p.text.strip():
                return p.text.strip()

    # 3 // find the first substantial paragraph in the body
    for p in soup.find_all('p'):
        text = p.text.strip()
        if len(text) > 50: 
            return text
    
    logger.warning(f"No suitable <p> tag found in the article {url}.")
    return "No content available."

# fetch POCKET articles
async def fetch_pocket_articles(pocket_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }

    def _sync_get(url):
        sc = cloudscraper.create_scraper()
        r = sc.get(url, headers=headers, timeout=15)
        return r.status_code, r.text

    try:
        status, body = await asyncio.to_thread(_sync_get, pocket_url)
        logger.info(f"fetch_pocket_articles: GET {pocket_url} -> {status} (len={len(body) if body else 0})")
        # 403 check bcs this website is playing games
        if status == 403:
            logger.error(f"403 received; response snippet: {body[:1000]!r}")
            return []
        if status != 200:
            logger.error(f"Error fetching the webpage: {pocket_url}. Status code: {status}")
            return []
    except Exception as e:
        logger.error(f"Request error while fetching {pocket_url}: {e}")
        return []

    soup = BeautifulSoup(body, 'html.parser')

    articles = soup.find_all('article', class_='featured-article-preview')
    fetched_articles = []
    for article in articles:
        title_tag = article.find('h2', class_='featured-article-preview__title')
        link_tag = article.find('a', class_='featured-article-preview__poster')
        image_tag = link_tag.find('img') if link_tag else None

        if title_tag and link_tag and image_tag:
            title = title_tag.text.strip()
            link = link_tag.get('href')
            if not link: 
                continue
            full_link = f"https://www.pokemon-zone.com{link}" if link.startswith("/") else link
            image_url = image_tag.get('src') or ""
            fetched_articles.append((title, full_link, image_url))

    logger.info(f"Fetched {len(fetched_articles)} articles from {pocket_url}.")
    return fetched_articles

# post articles
async def post_articles(channel, articles, role_mention=None, paragraph_fetcher=None):
    for article in articles:
        title = article[0]
        link = article[1]
        image_url = article[2]
        pre_fetched_paragraph = article[3] if len(article) > 3 else None

        first_paragraph = ""
        if pre_fetched_paragraph:
            first_paragraph = pre_fetched_paragraph
        elif paragraph_fetcher:
            try:
                result = paragraph_fetcher(link)
                if asyncio.iscoroutine(result):
                    first_paragraph = await result
                else:
                    first_paragraph = result
            except Exception as e:
                logger.error(f"Error fetching paragraph for {link}: {e}")
                first_paragraph = ""

        # try to get the full size image
        if image_url:
            # pattern to match -123x456.jpg/png etc at the end of the filename
            image_url = re.sub(r'-\d+x\d+(\.[a-zA-Z]+)$', r'\1', image_url)

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
            await asyncio.to_thread(database.save_posted_article, link)
            logger.info(f"Posted article: {title} - {link}")
        except Exception as e:
            logger.error(f"Failed to send message in channel {channel.id}: {e}")

# background task
@tasks.loop(hours=1)
async def check_and_post_articles():
    logger.info("Running hourly check for new articles...")
    posted_links = await asyncio.to_thread(database.load_posted_articles)

    # PTCG
    ptcg_channels = database.get_all_ptcg_channels()

    new_ptcg_articles = []
    all_articles = await fetch_ptcg_articles(PTCG_URL)
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
            
            role_id = database.get_ptcg_role(server_id)
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, new_ptcg_articles, role_mention=role_mention, paragraph_fetcher=fetch_first_paragraph)
    
    # POCKET
    pocket_channels = database.get_all_pocket_channels()

    new_pocket_articles = []
    all_articles = await fetch_pocket_articles(POCKET_URL)
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
            
            role_id = database.get_pocket_role(server_id) 
            role_mention = f"<@&{role_id}>" if role_id else None
            await post_articles(channel, new_pocket_articles, role_mention=role_mention, paragraph_fetcher=fetch_first_paragraph)

    logger.info("Finished hourly check.")

# slash commands
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
    database.save_ptcg_channel(server_id, str(channel.id))
    database.save_ptcg_role(server_id, str(role.id))

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
    database.save_pocket_channel(server_id, str(channel.id))
    database.save_pocket_role(server_id, str(role.id))

    await interaction.response.send_message(
        f"✅ Pocket updates will be posted in {channel.mention} and ping {role.mention}."
    )
    logger.info(f"/setpocket command run on server {server_id}. | Channel: {channel.id} - Role: {role.id}.")

# /update
@bot.tree.command(name="update", description="Check for news updates")
async def update(interaction: discord.Interaction):
    await interaction.response.send_message("Checking for new articles... ⏳", ephemeral=True)

    server_id = str(interaction.guild_id)
    channel_id = database.get_ptcg_channel(server_id)
    if not channel_id:
        await interaction.followup.send("No channel set. Use `/setptcg` first.", ephemeral=True)
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await interaction.followup.send("Invalid channel. Reset it with `/setptcg`.", ephemeral=True)
        return
    
    check_and_post_articles.restart()
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
    database.save_regex_pattern(server_id, pattern)

    await interaction.response.send_message(f"✅ Regex pattern set to: `{pattern}`")

    logger.info(f"/setregex command run on server {server_id}. | Pattern: {pattern}.")

# /removeregex
@bot.tree.command(name="removeregex", description="Remove the regex pattern for word checking")
async def removeregex(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    database.remove_regex_pattern(server_id)

    await interaction.response.send_message("✅ Regex pattern removed.")

    logger.info(f"/removeregex command run on server {server_id}.")

# /addignoredchannel
@bot.tree.command(name="addignoredchannel", description="Add a channel to be ignored by the regex check")
async def addignoredchannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    database.save_regex_ignored_channel(server_id, str(channel.id))

    await interaction.response.send_message(f"✅ Channel {channel.mention} has been added to the ignored list.")

    logger.info(f"/addignoredchannel command run on server {server_id}. | Channel: {channel.mention}.")

# /removeignoredchannel
@bot.tree.command(name="removeignoredchannel", description="Remove a channel to be ignored by the regex check")
async def removeignoredchannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    database.remove_regex_ignored_channel(server_id, str(channel.id))

    await interaction.response.send_message(f"✅ Channel {channel.mention} has been removed from the ignored list.")

    logger.info(f"/removeignoredchannel command run on server {server_id}. | Channel: {channel.mention}.")

# /listignoredchannels
@bot.tree.command(name="listignoredchannels", description="Lists all channels ignored by the regex check")
async def listignoredchannels(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
        return

    server_id = str(interaction.guild_id)
    ignored_channels = database.get_regex_ignored_channels(server_id)

    if ignored_channels:
        channels = [f"<#{channel_id}>" for channel_id in ignored_channels]
        await interaction.response.send_message(
            "✅ Ignored channels:\n" + "\n".join(channels)
        )
    else:
        await interaction.response.send_message("No channels are currently ignored.", ephemeral=True)

    logger.info(f"/listignoredchannels command run on server {server_id}.")

# EVENTS
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
    ignored_channels = database.get_regex_ignored_channels(server_id)

    # check if the message's channel or its parent (for forum posts) is ignored
    if str(message.channel.id) in ignored_channels or (
        hasattr(message.channel, "parent") and str(message.channel.parent.id) in ignored_channels
    ):
        return

    pattern = database.get_regex_pattern(server_id)
    if pattern and re.search(pattern, message.content, re.IGNORECASE):
        await message.reply(
            "👋🏽 Hey! It seems like you're looking to trade cards.\n\n"
            "We already have a specific channel for trading in PTCG Pocket so please read the post titled **READ ME** at the top of <#1334205216320655483> for more information. 🏛️\n"
            "If you're unable to make a listing, please grab the *Union Room* role at <#908131369085968394>!"
        )
        logger.info(f"Regex match triggered at server {server_id}.")

    await bot.process_commands(message)

bot.run(TOKEN)