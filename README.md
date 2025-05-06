# Ditto Bot

Invite link: https://discord.com/oauth2/authorize?client_id=1318567932661338183&permissions=2147502112&integration_type=0&scope=bot

## About

- A custom Discord bot built with Python using ```discord.py```. Features include automated moderation, user interaction commands, and integration with external APIs. Designed to be modular, scalable, and easy to extend for custom server needs.
- Hosted on personal Linux system

## Usage

*News Updates*

- **/setptcg <channel> <role>** - Set the channel and role for **PTCG** news updates.
- **/setpocket <channel> <role>** - Set the channel and role for **Pocket** news updates.
- **/update** - Run this command anywhere and it will check for any recent articles (normally checks every hour).

*Regex*

- **/setregex <pattern>** - Set a regex pattern for word checking.
- **/removeregex** - Remove the regex pattern.
- **/addignoredchannel <channel>** - Add a channel to be ignored by the regex check.
- **/removeignoredchannel <channel>** - Remove a channel to be ignored by the regex check.
- **/listignoredchannels** - Lists all channels ignored by the regex check.
- **/trading** - Manual command to tell users how to access the trading channels.

## Features

- **Automatic Updates -** Checks for updates every hour and automatically posts new articles to a discord channel.
- **Manual Updates -** Manual update checks using the **/update** command.
- **Channel & Role Settings -** Set a posting channel & role for each news topic.
- **Regex Word Matching -** Set a regex pattern for automatic checks.
- **Custom Embed -** Takes the article title, image, and first paragraph to create an embed link that is easy to read and understand.
- **SQLite Database -** Uses SQLite to manage posted articles, server channels, server roles, regex patterns, and ignored channels.
- **Activity Logging -** Logs every interaction to a local text file.