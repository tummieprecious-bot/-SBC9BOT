# Scheduling Bot

A Telegram bot for scheduling events and receiving reminders.

## Features
- 📅 Create events with title, date/time, and description
- 📋 View all scheduled events
- 📅 View today's events
- ❌ Cancel events
- ⏰ Automatic reminders

## Deployment

### Local Development
1. Clone the repository
2. Create a `.env` file with `TELEGRAM_BOT_TOKEN`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python bot.py`

### Deploy on Railway
1. Push code to GitHub
2. Connect repository to Railway
3. Add `TELEGRAM_BOT_TOKEN` as environment variable
4. Deploy!

## Commands
- `/start` - Welcome message
- `/schedule` - Create new event
- `/view` - View all events
- `/today` - View today's events
- `/cancel` - Cancel an event
- `/help` - Show help

## Technologies
- Python 3.9+
- python-telegram-bot
- Railway
