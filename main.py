import os
import logging
import json
import asyncio
import threading

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from flask_server import set_user_flow, credentials_event, app as flask_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIRECT_URL = os.getenv("REDIRECT_URL")
SCOPES = ['https://www.googleapis.com/auth/drive.file']
credentials_info = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))

# Store credentials per user
user_credentials = {}

# Command handler for /start
async def start(update: Update, context):
    try:
        user_id = update.effective_user.id
        logger.info(f"Start command from user {user_id}")

        flow = InstalledAppFlow.from_client_config(credentials_info, SCOPES)
        flow.redirect_uri = REDIRECT_URL

        auth_url, _ = flow.authorization_url(
            prompt='consent', access_type='offline', state=str(user_id)
        )

        set_user_flow(str(user_id), flow)

        await update.message.reply_text(
            f"🔐 Authorize the bot to access your Google Drive:\n{auth_url}\n\n"
            "Return here after authorizing."
        )

        await update.message.reply_text("⏳ Waiting for authorization...")

        if credentials_event.wait(timeout=60):
            user_credentials[user_id] = flow.credentials
            await update.message.reply_text("✅ Authorized! Now send me a file.")
        else:
            await update.message.reply_text("❌ Timeout. Please try /start again.")
    except Exception as e:
        logger.error(f"[Start Error] {e}")
        await update.message.reply_text("❌ Authorization error occurred.")

# File upload handler
async def handle_file(update: Update, context):
    user_id = update.effective_user.id
    creds = user_credentials.get(user_id)

    if not creds:
        await update.message.reply_text("⚠️ Please run /start to authorize first.")
        return

    try:
        service = build('drive', 'v3', credentials=creds)

        # Ensure "savepanra" folder exists
        folder_name = "savepanra"
        folder_id = None

        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        ).execute()
        folders = results.get('files', [])
        folder_id = folders[0]['id'] if folders else None

        if not folder_id:
            folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder['id']

        # Download file
        doc = update.message.document
        tg_file = await doc.get_file()
        local_path = f"temp/{doc.file_name}"
        os.makedirs("temp", exist_ok=True)
        await tg_file.download_to_drive(local_path)

        # Upload to Drive
        file_metadata = {'name': doc.file_name, 'parents': [folder_id]}
        media = MediaFileUpload(local_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        os.remove(local_path)
        await update.message.reply_text("✅ File uploaded to Google Drive.")
    except Exception as e:
        logger.error(f"[Upload Error] {e}")
        await update.message.reply_text("❌ Upload failed. Try again.")

# Start Telegram bot
async def start_telegram_bot():
    logger.info("Starting Telegram bot...")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    logger.info("🚀 Bot is running.")
    await app.run_polling()

# Start Flask server in thread
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

# Entrypoint
async def main():
    # Ensure the event loop is compatible
    import nest_asyncio
    nest_asyncio.apply()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start the Telegram bot asynchronously
    await start_telegram_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise e
