# Pokemon TCG News Bot

Invite link: https://discord.com/oauth2/authorize?client_id=1318567932661338183&permissions=2147502112&integration_type=0&scope=bot

## About

- A simple Discord bot that scrapes the web for news relating to the Pokemon TCG and posts them to a channel.
- Python
- Bot hosted on personal Linux system
- Articles from https://www.pokebeach.com/

## Usage

- **/ptcgnews -** Run this command anywhere and it will check for any recent articles. If new articles are found, the bot will post them on the channel set by /setchannel along with a notification to the role set by /setrole.
- **/setchannel -** Run this command followed by the channel that you want to set. The bot will post updates to that channel.
- **/setrole -** Run this command followed by the role that you want to set. The bot will notify that role whenever a new article is posted.

## Features

- **Automatic Updates -** Checks for updates every hour and automatically posts new articles to a discord channel.
- **Manual Updates -** Manual update checks using the **/ptcgnews** command.
- **Channel Settings -** Set a posting channel using the **/setchannel** command.
- **Role Settings -** Set a notification role using the **/setrole** command.
- **Custom Embed -** Takes the article title, image, and first paragraph to create an embed link that is easy to read and understand.
- **SQLite Database -** Uses SQLite to manage posted articles, server channels, and roles.
- **Activity Logging -** Logs every interaction to a local text file.