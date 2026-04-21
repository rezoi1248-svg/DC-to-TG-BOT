# Discord to Telegram Reposter Bot

## Setup Guide for Beginners

### 1. Create Discord Bot
1. Go to https://discord.com/developers/applications
2. Click "New Application" → Give it a name
3. Go to "Bot" tab → Click "Add Bot"
4. Copy the token (keep it secret!)
5. Enable "Message Content Intent" under Privileged Gateway Intents

### 2. Get Discord Channel ID
1. Enable Developer Mode in Discord (Settings → Advanced)
2. Right-click on your target channel → "Copy Channel ID"

### 3. Create Telegram Bot
1. Open Telegram → Search for @BotFather
2. Send `/newbot` and follow instructions
3. Copy the bot token

### 4. Get Telegram Channel ID
1. Add your bot as admin to your channel
2. Send any message to the channel
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find "chat" → "id" (negative number for channels)

### 5. Deploy on Railway

#### Method 1: Direct Deploy
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

#### Method 2: Manual Deploy
1. Push code to GitHub
2. Login to Railway.app
3. "New Project" → "Deploy from GitHub repo"
4. Add environment variables in Railway dashboard
5. Deploy!

### Environment Variables
Copy these to Railway:
- `DISCORD_TOKEN` = Your Discord bot token
- `DISCORD_CHANNEL_ID` = Discord channel ID to monitor
- `TELEGRAM_TOKEN` = Your Telegram bot token  
- `TELEGRAM_CHANNEL_ID` = Telegram channel ID (with -100 prefix)
- `LOG_LEVEL` = INFO (optional)
- `MAX_FILE_SIZE` = 20 (optional, in MB)

### Running Locally (Test)
```bash
pip install -r requirements.txt
python main.py