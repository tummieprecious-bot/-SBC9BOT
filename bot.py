import os
import logging
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import pytz

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    exit(1)

# Flask app
app = Flask(__name__)

# Store schedules
user_schedules = {}
TZ = pytz.timezone("Asia/Kolkata")

def get_user_schedule(user_id):
    if user_id not in user_schedules:
        user_schedules[user_id] = []
    return user_schedules[user_id]

# ---------- COMMAND HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = (
        f"👋 Welcome {user.first_name}!\n\n"
        "I'm your Scheduling Bot! 🗓️\n\n"
        "/schedule - Create a new event\n"
        "/view - View all events\n"
        "/today - Today's events\n"
        "/cancel - Cancel an event\n"
        "/help - Get help"
    )
    await update.message.reply_text(welcome)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 Commands:\n\n"
        "/start - Welcome\n"
        "/schedule - Schedule event\n"
        "/view - View all events\n"
        "/today - Today's events\n"
        "/cancel - Cancel event\n"
        "/help - This help\n\n"
        "To schedule:\n"
        "1. Click /schedule\n"
        "2. Enter event title\n"
        "3. Enter date/time (YYYY-MM-DD HH:MM)\n"
        "4. Enter description (or type 'skip')"
    )
    await update.message.reply_text(help_text)

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Schedule Event", callback_data="schedule_event")],
        [InlineKeyboardButton("📋 View Events", callback_data="view_events")],
        [InlineKeyboardButton("📅 Today's Events", callback_data="today_events")],
    ]
    await update.message.reply_text(
        "What would you like to do? 🤔",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    schedules = get_user_schedule(user_id)
    
    if not schedules:
        await update.message.reply_text("📭 No scheduled events.")
        return
    
    msg = "📅 Your Events:\n\n"
    for i, e in enumerate(schedules, 1):
        msg += f"{i}. 📌 {e['title']}\n"
        msg += f"   🕐 {e['datetime'].strftime('%B %d, %I:%M %p')}\n"
        msg += f"   📝 {e.get('description', 'No description')}\n\n"
    
    await update.message.reply_text(msg)

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now(TZ).date()
    schedules = get_user_schedule(user_id)
    today_events = [e for e in schedules if e['datetime'].date() == today]
    
    if not today_events:
        await update.message.reply_text("📭 No events today.")
        return
    
    msg = f"📅 Today ({today.strftime('%B %d, %Y')}):\n\n"
    for i, e in enumerate(today_events, 1):
        msg += f"{i}. 📌 {e['title']} - {e['datetime'].strftime('%I:%M %p')}\n"
    
    await update.message.reply_text(msg)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    schedules = get_user_schedule(user_id)
    
    if not schedules:
        await update.message.reply_text("📭 No events to cancel.")
        return
    
    keyboard = []
    for i, e in enumerate(schedules, 1):
        btn = f"{i}. {e['title']} ({e['datetime'].strftime('%b %d, %I:%M %p')})"
        keyboard.append([InlineKeyboardButton(btn, callback_data=f"cancel_{i-1}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_menu")])
    await update.message.reply_text(
        "Select event to cancel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- CALLBACK HANDLERS ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "schedule_event":
        context.user_data['scheduling'] = True
        context.user_data['step'] = 'title'
        await query.edit_message_text(
            "📝 Enter event title:\n(Send /cancel to abort)"
        )
    
    elif data == "view_events":
        schedules = get_user_schedule(user_id)
        if not schedules:
            await query.edit_message_text("📭 No events.")
            return
        msg = "📅 Your Events:\n\n"
        for i, e in enumerate(schedules, 1):
            msg += f"{i}. {e['title']} - {e['datetime'].strftime('%b %d, %I:%M %p')}\n"
        await query.edit_message_text(msg)
    
    elif data == "today_events":
        today = datetime.now(TZ).date()
        schedules = get_user_schedule(user_id)
        today_events = [e for e in schedules if e['datetime'].date() == today]
        if not today_events:
            await query.edit_message_text("📭 No events today.")
            return
        msg = f"📅 Today:\n\n"
        for i, e in enumerate(today_events, 1):
            msg += f"{i}. {e['title']} - {e['datetime'].strftime('%I:%M %p')}\n"
        await query.edit_message_text(msg)
    
    elif data == "cancel_menu":
        await query.edit_message_text("❌ Cancelled.")
    
    elif data.startswith("cancel_"):
        try:
            idx = int(data.split("_")[1])
            schedules = get_user_schedule(user_id)
            if 0 <= idx < len(schedules):
                removed = schedules.pop(idx)
                await query.edit_message_text(f"✅ Cancelled: {removed['title']}")
            else:
                await query.edit_message_text("❌ Not found.")
        except:
            await query.edit_message_text("❌ Error.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.user_data.get('scheduling'):
        await update.message.reply_text("Use /schedule to start.")
        return
    
    step = context.user_data.get('step')
    text = update.message.text
    
    if text == "/cancel":
        context.user_data['scheduling'] = False
        context.user_data['step'] = None
        await update.message.reply_text("❌ Cancelled.")
        return
    
    if step == 'title':
        context.user_data['event_title'] = text
        context.user_data['step'] = 'datetime'
        await update.message.reply_text(
            "🕐 Enter date/time:\nFormat: YYYY-MM-DD HH:MM\nExample: 2026-12-25 18:30"
        )
    
    elif step == 'datetime':
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            dt = TZ.localize(dt)
            if dt < datetime.now(TZ):
                await update.message.reply_text("⚠️ Time is in the past. Try again.")
                return
            context.user_data['event_datetime'] = dt
            context.user_data['step'] = 'description'
            await update.message.reply_text(
                "📝 Enter description (or type 'skip'):"
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use: YYYY-MM-DD HH:MM")
    
    elif step == 'description':
        title = context.user_data['event_title']
        dt = context.user_data['event_datetime']
        desc = text if text.lower() != 'skip' else "No description"
        
        schedules = get_user_schedule(user_id)
        schedules.append({'title': title, 'datetime': dt, 'description': desc})
        
        context.user_data['scheduling'] = False
        context.user_data['step'] = None
        
        await update.message.reply_text(
            f"✅ Scheduled!\n\n📌 {title}\n🕐 {dt.strftime('%B %d, %I:%M %p')}\n📝 {desc}"
        )

# ---------- FLASK WEBHOOK ----------
@app.route('/')
def home():
    return "Bot is running! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Get the update from Telegram
        update_data = request.get_json()
        if update_data:
            update = Update.de_json(update_data, application.bot)
            application.process_update(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# ---------- MAIN ----------
if __name__ == '__main__':
    print("🤖 Starting bot with webhook...")
    print(f"Token present: {'Yes' if TOKEN else 'No'}")
    
    # Build application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("view", view_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Set webhook
    webhook_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if webhook_url:
        webhook_url = f"https://{webhook_url}/webhook"
        print(f"Webhook URL: {webhook_url}")
        application.bot.set_webhook(webhook_url)
        print("✅ Webhook set!")
    else:
        print("⚠️ No webhook URL. Running with polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    # Start Flask server
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
