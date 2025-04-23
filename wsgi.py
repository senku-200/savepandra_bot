# wsgi.py
import threading
import nest_asyncio
nest_asyncio.apply()

from flask_server import run_flask_server
from main import start_telegram_bot
import asyncio

def start_flask():
    run_flask_server()

# Start Flask server in a background thread
flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# Run the Telegram bot in the main thread event loop
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_telegram_bot())
