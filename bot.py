import os
import logging
import sys
from flask import Flask, request, jsonify
import requests
import json

# Force flush logs
sys.stdout.flush()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get bot token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
    sys.exit(1)

logger.info(f"✅ Token found: {TOKEN[:10]}...")

# Telegram API URL
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"

# Store user data
user_data = {}

# ---------- TELEGRAM HELPERS ----------
def send_message(chat_id, text, reply_markup=None):
    """Send a message to Telegram"""
    url = f"{TELEGRAM_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload)
        logger.info(f"📤 Sent message to {chat_id}: {response.status_code}")
        return response.json()
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        return None

def send_start_keyboard(chat_id):
    """Send welcome message"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "📝 Schedule Event", "callback_data": "schedule"}],
            [{"text": "📋 View Events", "callback_data": "view"}],
            [{"text": "📅 Today's Events", "callback_data": "today"}]
        ]
    }
    text = (
        "👋 <b>Welcome to Scheduling Bot!</b>\n\n"
        "I'll help you manage your schedule.\n\n"
        "📝 Schedule new events\n"
        "📋 View all your events\n"
        "📅 See today's events\n\n"
        "Click a button below to get started!"
    )
    return send_message(chat_id, text, keyboard)

# ---------- PROCESS UPDATES ----------
def process_update(update):
    """Process incoming update"""
    try:
        logger.info(f"📨 Processing update: {update}")
        
        # Handle callback queries
        if 'callback_query' in update:
            query = update['callback_query']
            chat_id = query['from']['id']
            data = query['data']
            
            # Answer callback
            requests.post(f"{TELEGRAM_URL}/answerCallbackQuery", json={
                "callback_query_id": query['id']
            })
            
            if data == "schedule":
                send_message(chat_id, 
                    "📝 <b>Create New Event</b>\n\n"
                    "Send me the event details in this format:\n"
                    "<code>Title | YYYY-MM-DD HH:MM | Description</code>\n\n"
                    "Example:\n"
                    "<code>Meeting | 2026-08-05 15:00 | Team sync</code>"
                )
                user_data[f"{chat_id}_state"] = "awaiting_schedule"
            
            elif data == "view":
                events = user_data.get(chat_id, [])
                if not events:
                    send_message(chat_id, "📭 No scheduled events.")
                    return
                
                text = "📅 <b>Your Events:</b>\n\n"
                for i, event in enumerate(events, 1):
                    text += f"{i}. <b>{event['title']}</b>\n"
                    text += f"   🕐 {event['datetime']}\n"
                    text += f"   📝 {event.get('description', 'No description')}\n\n"
                send_message(chat_id, text)
            
            elif data == "today":
                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                events = user_data.get(chat_id, [])
                today_events = [e for e in events if e['datetime'].startswith(today)]
                
                if not today_events:
                    send_message(chat_id, f"📭 No events today ({today}).")
                    return
                
                text = f"📅 <b>Today's Events ({today}):</b>\n\n"
                for i, event in enumerate(today_events, 1):
                    time = event['datetime'].split()[1]
                    text += f"{i}. <b>{event['title']}</b> at {time}\n"
                send_message(chat_id, text)
        
        # Handle messages
        elif 'message' in update:
            message = update['message']
            chat_id = message['from']['id']
            text = message.get('text', '')
            
            logger.info(f"💬 Message from {chat_id}: {text}")
            
            if text == '/start':
                send_start_keyboard(chat_id)
            
            elif user_data.get(f"{chat_id}_state") == "awaiting_schedule":
                try:
                    parts = text.split('|')
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        datetime_str = parts[1].strip()
                        description = parts[2].strip() if len(parts) >= 3 else "No description"
                        
                        # Validate date
                        from datetime import datetime as dt
                        dt.strptime(datetime_str, "%Y-%m-%d %H:%M")
                        
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
                            f"📝 {description}"
                        )
                    else:
                        send_message(chat_id, 
                            "❌ Invalid format. Use:\n"
                            "<code>Title | YYYY-MM-DD HH:MM | Description</code>"
                        )
                except Exception as e:
                    send_message(chat_id, f"❌ Error: {str(e)}")
            
            else:
                send_message(chat_id, "👋 Send /start to begin!")
    
    except Exception as e:
        logger.error(f"❌ Process error: {e}")

# ---------- FLASK ROUTES ----------
@app.route('/', methods=['GET'])
def home():
    return "✅ Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json()
        logger.info(f"📨 Webhook received: {update}")
        if update:
            process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return "Error", 500

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint"""
    return jsonify({
        "status": "running",
        "token_set": bool(TOKEN),
        "domain": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "Not set")
    })

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    """Set webhook"""
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not domain:
        return "❌ RAILWAY_PUBLIC_DOMAIN not set", 400
    
    webhook_url = f"https://{domain}/webhook"
    url = f"{TELEGRAM_URL}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(url)
        logger.info(f"Webhook response: {response.json()}")
        return jsonify(response.json()), 200
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/deletewebhook', methods=['GET'])
def delete_webhook():
    """Delete webhook"""
    url = f"{TELEGRAM_URL}/deleteWebhook"
    try:
        response = requests.get(url)
        return jsonify(response.json()), 200
    except Exception as e:
        return f"Error: {e}", 500

# ---------- MAIN ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("🚀 Starting bot...")
    logger.info(f"📡 Port: {port}")
    
    # Set webhook
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        webhook_url = f"https://{domain}/webhook"
        url = f"{TELEGRAM_URL}/setWebhook?url={webhook_url}"
        try:
            response = requests.get(url)
            logger.info(f"✅ Webhook set: {response.json()}")
        except Exception as e:
            logger.error(f"❌ Failed to set webhook: {e}")
    else:
        logger.warning("⚠️ RAILWAY_PUBLIC_DOMAIN not set!")
        logger.warning("Please add it in Railway variables")
    
    # Test bot
    try:
        response = requests.get(f"{TELEGRAM_URL}/getMe")
        logger.info(f"✅ Bot info: {response.json()}")
    except Exception as e:
        logger.error(f"❌ Cannot connect to Telegram: {e}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
