# Ditto Bot

Invite link: https://discord.com/oauth2/authorize?client_id=1318567932661338183&permissions=2147502112&integration_type=0&scope=bot

## About

- A simple Discord bot that scrapes the web for news relating to the Pokemon TCG/Pocket and posts them to a channel.
- Python
- Bot hosted on personal Linux system

## Usage

- **/setptcg <channel> <role> -** Set the channel and role for **PTCG** news updates.
- **/setpocket <channel> <role> -** Set the channel and role for **Pocket** news updates.
- **/update -** Run this command anywhere and it will check for any recent articles (normally checks every hour).

## Features

- **Automatic Updates -** Checks for updates every hour and automatically posts new articles to a discord channel.
- **Manual Updates -** Manual update checks using the **/update** command.
- **Channel Settings -** Set a posting channel for each news topic.
- **Role Settings -** Set a notification role for each news topic.
- **Custom Embed -** Takes the article title, image, and first paragraph to create an embed link that is easy to read and understand.
- **SQLite Database -** Uses SQLite to manage posted articles, server channels, and roles.
- **Activity Logging -** Logs every interaction to a local text file.