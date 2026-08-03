import os
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import pytz

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Store schedules (in production, use a database)
user_schedules = {}

# Timezone
TZ = pytz.timezone("Asia/Kolkata")  # Change to your timezone

# Helper functions
def get_user_schedule(user_id):
    if user_id not in user_schedules:
        user_schedules[user_id] = []
    return user_schedules[user_id]

def format_schedule(schedules):
    if not schedules:
        return "📭 You have no scheduled events."
    
    message = "📅 Your Scheduled Events:\n\n"
    for idx, event in enumerate(schedules, 1):
        message += f"{idx}. 📌 {event['title']}\n"
        message += f"   🕐 {event['datetime'].strftime('%B %d, %Y at %I:%M %p')}\n"
        message += f"   📝 {event.get('description', 'No description')}\n\n"
    return message

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    welcome_text = (
        f"👋 Welcome {user.first_name}!\n\n"
        "I'm your personal Scheduling Bot. Here's what I can do:\n\n"
        "📌 /schedule - Create a new event\n"
        "📋 /view - View all your scheduled events\n"
        "❌ /cancel - Cancel an event\n"
        "📅 /today - View today's events\n"
        "ℹ️ /help - Show this help message\n\n"
        "Let's get you organized! 🚀"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_text = (
        "📋 **Available Commands:**\n\n"
        "/start - Start the bot\n"
        "/schedule - Schedule a new event\n"
        "/view - View all events\n"
        "/cancel - Cancel an event\n"
        "/today - View today's events\n"
        "/help - Show this help\n\n"
        "**How to schedule:**\n"
        "1. Click /schedule\n"
        "2. Follow the prompts\n"
        "3. I'll remind you at the scheduled time! ⏰"
    )
    await update.message.reply_text(help_text)

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the scheduling process."""
    keyboard = [
        [InlineKeyboardButton("📝 Schedule Event", callback_data="schedule_event")],
        [InlineKeyboardButton("📋 View All Events", callback_data="view_events")],
        [InlineKeyboardButton("📅 Today's Events", callback_data="today_events")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "What would you like to do? 🤔",
        reply_markup=reply_markup
    )

async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all scheduled events."""
    user_id = update.effective_user.id
    schedules = get_user_schedule(user_id)
    message = format_schedule(schedules)
    await update.message.reply_text(message)

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View today's events."""
    user_id = update.effective_user.id
    today = datetime.now(TZ).date()
    
    schedules = get_user_schedule(user_id)
    today_events = [e for e in schedules if e['datetime'].date() == today]
    
    if not today_events:
        await update.message.reply_text("📭 You have no events scheduled for today.")
        return
    
    message = f"📅 Today's Events ({today.strftime('%B %d, %Y')}):\n\n"
    for idx, event in enumerate(today_events, 1):
        message += f"{idx}. 📌 {event['title']}\n"
        message += f"   🕐 {event['datetime'].strftime('%I:%M %p')}\n\n"
    
    await update.message.reply_text(message)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel an event."""
    user_id = update.effective_user.id
    schedules = get_user_schedule(user_id)
    
    if not schedules:
        await update.message.reply_text("📭 You have no events to cancel.")
        return
    
    # Create inline keyboard with events
    keyboard = []
    for idx, event in enumerate(schedules, 1):
        button_text = f"{idx}. {event['title']} - {event['datetime'].strftime('%B %d, %I:%M %p')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"cancel_{idx-1}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select the event to cancel:",
        reply_markup=reply_markup
    )

# Callback Query Handlers
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "schedule_event":
        context.user_data['scheduling'] = True
        context.user_data['step'] = 'title'
        await query.edit_message_text(
            "📝 Please enter the event title:\n\n"
            "(Send /cancel_schedule to cancel)"
        )
    
    elif data == "view_events":
        schedules = get_user_schedule(user_id)
        message = format_schedule(schedules)
        await query.edit_message_text(message)
    
    elif data == "today_events":
        today = datetime.now(TZ).date()
        schedules = get_user_schedule(user_id)
        today_events = [e for e in schedules if e['datetime'].date() == today]
        
        if not today_events:
            await query.edit_message_text("📭 No events scheduled for today.")
            return
        
        message = f"📅 Today's Events ({today.strftime('%B %d, %Y')}):\n\n"
        for idx, event in enumerate(today_events, 1):
            message += f"{idx}. 📌 {event['title']}\n"
            message += f"   🕐 {event['datetime'].strftime('%I:%M %p')}\n\n"
        await query.edit_message_text(message)
    
    elif data == "cancel_menu":
        await query.edit_message_text("Operation cancelled.")
    
    elif data.startswith("cancel_"):
        try:
            idx = int(data.split("_")[1])
            schedules = get_user_schedule(user_id)
            
            if 0 <= idx < len(schedules):
                removed = schedules.pop(idx)
                await query.edit_message_text(
                    f"✅ Event cancelled: **{removed['title']}**",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Event not found.")
        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid selection.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages during scheduling."""
    user_id = update.effective_user.id
    
    if not context.user_data.get('scheduling'):
        await update.message.reply_text(
            "Please use /schedule to start scheduling an event."
        )
        return
    
    step = context.user_data.get('step')
    text = update.message.text
    
    if text == "/cancel_schedule":
        context.user_data['scheduling'] = False
        context.user_data['step'] = None
        await update.message.reply_text("❌ Scheduling cancelled.")
        return
    
    if step == 'title':
        context.user_data['event_title'] = text
        context.user_data['step'] = 'datetime'
        await update.message.reply_text(
            "🕐 Please enter the date and time for the event:\n\n"
            "Format: `YYYY-MM-DD HH:MM` (24-hour)\n"
            "Example: `2026-12-25 18:30`\n\n"
            "Send /cancel_schedule to cancel.",
            parse_mode="Markdown"
        )
    
    elif step == 'datetime':
        try:
            # Parse datetime
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            dt = TZ.localize(dt)
            
            if dt < datetime.now(TZ):
                await update.message.reply_text(
                    "⚠️ This time is in the past. Please enter a future date and time."
                )
                return
            
            context.user_data['event_datetime'] = dt
            context.user_data['step'] = 'description'
            await update.message.reply_text(
                "📝 Please enter a description for the event (optional):\n\n"
                "Type 'skip' to skip this step.\n"
                "Send /cancel_schedule to cancel."
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid format. Please use: `YYYY-MM-DD HH:MM`\n"
                "Example: `2026-12-25 18:30`",
                parse_mode="Markdown"
            )
    
    elif step == 'description':
        title = context.user_data['event_title']
        dt = context.user_data['event_datetime']
        description = text if text.lower() != 'skip' else "No description"
        
        # Save event
        schedules = get_user_schedule(user_id)
        schedules.append({
            'title': title,
            'datetime': dt,
            'description': description
        })
        
        # Reset scheduling state
        context.user_data['scheduling'] = False
        context.user_data['step'] = None
        
        await update.message.reply_text(
            f"✅ Event scheduled successfully!\n\n"
            f"📌 **{title}**\n"
            f"🕐 {dt.strftime('%B %d, %Y at %I:%M %p')}\n"
            f"📝 {description}\n\n"
            "I'll remind you at the scheduled time! ⏰",
            parse_mode="Markdown"
        )

# Main function
def main():
    """Start the bot."""
    # Create Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("view", view_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler for scheduling
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    print("🤖 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
