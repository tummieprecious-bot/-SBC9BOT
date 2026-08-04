import os
import logging
from flask import Flask, request, jsonify
import requests

# Simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get bot token from environment
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    exit(1)

# Telegram API URL
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"

# Store user data (in-memory)
user_data = {}

# ---------- TELEGRAM API HELPERS ----------
def send_message(chat_id, text, reply_markup=None):
    """Send a message to Telegram"""
    url = f"{TELEGRAM_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

def send_start_keyboard(chat_id):
    """Send welcome message with keyboard"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "📝 Schedule Event", "callback_data": "schedule"}],
            [{"text": "📋 View Events", "callback_data": "view"}],
            [{"text": "📅 Today's Events", "callback_data": "today"}]
        ]
    }
    text = (
        "👋 <b>Welcome to Scheduling Bot!</b>\n\n"
        "I'll help you manage your schedule. Here's what I can do:\n\n"
        "📝 Schedule new events\n"
        "📋 View all your events\n"
        "📅 See today's events\n\n"
        "Just click a button below to get started!"
    )
    return send_message(chat_id, text, keyboard)

def show_events(chat_id):
    """Show all events for a user"""
    events = user_data.get(chat_id, [])
    if not events:
        send_message(chat_id, "📭 You have no scheduled events.")
        return
    
    text = "📅 <b>Your Scheduled Events:</b>\n\n"
    for i, event in enumerate(events, 1):
        text += f"{i}. <b>{event['title']}</b>\n"
        text += f"   🕐 {event['datetime']}\n"
        text += f"   📝 {event.get('description', 'No description')}\n\n"
    
    # Add cancel button
    keyboard = {
        "inline_keyboard": [
            [{"text": "❌ Cancel Event", "callback_data": "cancel"}],
            [{"text": "🔙 Back to Menu", "callback_data": "menu"}]
        ]
    }
    send_message(chat_id, text, keyboard)

def show_today_events(chat_id):
    """Show today's events"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    events = user_data.get(chat_id, [])
    today_events = [e for e in events if e['datetime'].startswith(today)]
    
    if not today_events:
        send_message(chat_id, f"📭 No events scheduled for today ({today}).")
        return
    
    text = f"📅 <b>Today's Events ({today}):</b>\n\n"
    for i, event in enumerate(today_events, 1):
        time = event['datetime'].split()[1]
        text += f"{i}. <b>{event['title']}</b> at {time}\n"
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔙 Back to Menu", "callback_data": "menu"}]
        ]
    }
    send_message(chat_id, text, keyboard)

# ---------- PROCESS UPDATES ----------
def process_update(update):
    """Process incoming Telegram update"""
    try:
        # Handle callback queries (button presses)
        if 'callback_query' in update:
            query = update['callback_query']
            chat_id = query['from']['id']
            data = query['data']
            
            # Answer callback to remove loading state
            requests.post(f"{TELEGRAM_URL}/answerCallbackQuery", json={
                "callback_query_id": query['id']
            })
            
            if data == "menu":
                send_start_keyboard(chat_id)
            
            elif data == "schedule":
                send_message(chat_id, 
                    "📝 <b>Create New Event</b>\n\n"
                    "Please send me the event details in this format:\n"
                    "<code>Title | YYYY-MM-DD HH:MM | Description</code>\n\n"
                    "Example:\n"
                    "<code>Meeting | 2026-08-05 15:00 | Team sync</code>\n\n"
                    "Or send <b>/cancel</b> to abort."
                )
                # Store state
                user_data[f"{chat_id}_state"] = "awaiting_schedule"
            
            elif data == "view":
                show_events(chat_id)
            
            elif data == "today":
                show_today_events(chat_id)
            
            elif data == "cancel":
                events = user_data.get(chat_id, [])
                if not events:
                    send_message(chat_id, "📭 No events to cancel.")
                    return
                
                # Show events with cancel buttons
                text = "❌ <b>Select event to cancel:</b>\n\n"
                keyboard = {"inline_keyboard": []}
                for i, event in enumerate(events, 1):
                    text += f"{i}. {event['title']} - {event['datetime']}\n"
                    keyboard["inline_keyboard"].append([
                        {"text": f"Cancel #{i}", "callback_data": f"cancel_{i-1}"}
                    ])
                keyboard["inline_keyboard"].append([
                    {"text": "🔙 Back", "callback_data": "menu"}
                ])
                send_message(chat_id, text, keyboard)
            
            elif data.startswith("cancel_"):
                try:
                    idx = int(data.split("_")[1])
                    events = user_data.get(chat_id, [])
                    if 0 <= idx < len(events):
                        removed = events.pop(idx)
                        send_message(chat_id, f"✅ Cancelled: <b>{removed['title']}</b>")
                        show_events(chat_id)
                    else:
                        send_message(chat_id, "❌ Event not found.")
                except Exception as e:
                    send_message(chat_id, "❌ Error cancelling event.")
        
        # Handle text messages
        elif 'message' in update:
            message = update['message']
            chat_id = message['from']['id']
            text = message.get('text', '')
            
            # Handle /start command
            if text == '/start':
                send_start_keyboard(chat_id)
            
            # Handle /cancel command
            elif text == '/cancel':
                user_data[f"{chat_id}_state"] = None
                send_message(chat_id, "❌ Operation cancelled. Use /start to begin again.")
            
            # Handle scheduling input
            elif user_data.get(f"{chat_id}_state") == "awaiting_schedule":
                try:
                    # Parse input: Title | YYYY-MM-DD HH:MM | Description
                    parts = text.split('|')
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        datetime_str = parts[1].strip()
                        description = parts[2].strip() if len(parts) >= 3 else "No description"
                        
                        # Validate date format
                        from datetime import datetime as dt
                        dt.strptime(datetime_str, "%Y-%m-%d %H:%M")
                        
                        # Save event
                        if chat_id not in user_data:
                            user_data[chat_id] = []
                        user_data[chat_id].append({
                            'title': title,
                            'datetime': datetime_str,
                            'description': description
                        })
                        
                        user_data[f"{chat_id}_state"] = None
                        send_message(chat_id, 
                            f"✅ <b>Event Scheduled!</b>\n\n"
                            f"📌 {title}\n"
                            f"🕐 {datetime_str}\n"
                            f"📝 {description}\n\n"
                            f"Use /start to manage your events."
                        )
                    else:
                        send_message(chat_id, 
                            "❌ Invalid format.\n\n"
                            "Please use:\n"
                            "<code>Title | YYYY-MM-DD HH:MM | Description</code>\n\n"
                            "Example:\n"
                            "<code>Meeting | 2026-08-05 15:00 | Team sync</code>"
                        )
                except Exception as e:
                    send_message(chat_id, 
                        f"❌ Error: Invalid date format.\n\n"
                        f"Please use: <code>YYYY-MM-DD HH:MM</code>\n"
                        f"Example: <code>2026-08-05 15:00</code>"
                    )
            
            # Handle any other text
            else:
                send_message(chat_id, 
                    "👋 Use /start to see the menu and manage your schedule!"
                )
    
    except Exception as e:
        logger.error(f"Error processing update: {e}")

# ---------- FLASK ROUTES ----------
@app.route('/', methods=['GET'])
def home():
    return "✅ Bot is running! Send /start to your bot on Telegram."

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        if update:
            logger.info(f"Received update: {update.get('message', {}).get('text', 'callback')}")
            process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    """Manually set webhook"""
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if not domain:
        return "❌ RAILWAY_PUBLIC_DOMAIN not set", 400
    
    webhook_url = f"https://{domain}/webhook"
    url = f"{TELEGRAM_URL}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(url)
        return f"Webhook set to: {webhook_url}\nResponse: {response.json()}", 200
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/deletewebhook', methods=['GET'])
def delete_webhook():
    """Delete webhook (fallback to polling)"""
    url = f"{TELEGRAM_URL}/deleteWebhook"
    try:
        response = requests.get(url)
        return f"Webhook deleted: {response.json()}", 200
    except Exception as e:
        return f"Error: {e}", 500

# ---------- MAIN ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    
    # Set webhook on startup
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if domain:
        webhook_url = f"https://{domain}/webhook"
        url = f"{TELEGRAM_URL}/setWebhook?url={webhook_url}"
        try:
            response = requests.get(url)
            logger.info(f"✅ Webhook set: {response.json()}")
        except Exception as e:
            logger.error(f"❌ Failed to set webhook: {e}")
    else:
        logger.warning("⚠️ No RAILWAY_PUBLIC_DOMAIN set. Using fallback...")
    
    logger.info(f"🚀 Starting bot on port {port}")
    app.run(host='0.0.0.0', port=port)
