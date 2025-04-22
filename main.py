import os
import time
import threading
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from flask_server import run_flask_server, set_flow, credentials_event

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SCOPES = ['https://www.googleapis.com/auth/drive.file']
user_credentials = {}

# Start Flask OAuth server in background
threading.Thread(target=run_flask_server, daemon=True).start()

async def start(update: Update, context):
    try:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        flow.redirect_uri = 'http://localhost:8080/'
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

        set_flow(flow)
        await update.message.reply_text(
            f"🔐 Authorize the bot to access your Google Drive:\n{auth_url}\n\n"
            "Return after authorizing."
        )

        await update.message.reply_text("⏳ Waiting for authorization...")

        if credentials_event.wait(timeout=60):  # Wait up to 60 seconds
            user_credentials[update.effective_user.id] = flow.credentials
            await update.message.reply_text("✅ Authorized successfully! Now send me a file.")
        else:
            await update.message.reply_text("❌ Timeout. Please try /start again.")
    except Exception as e:
        print(f"[Start Error] {e}")
        await update.message.reply_text("❌ Authorization error occurred.")

async def handle_file(update: Update, context):
    user_id = update.effective_user.id
    creds = user_credentials.get(user_id)

    if not creds:
        await update.message.reply_text("⚠️ Use /start to authorize first.")
        return

    try:
        service = build('drive', 'v3', credentials=creds)

        # Ensure "savepanra" folder exists
        folder_name = "savepanra"
        folder_id = None
        results = service.files().list(q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false").execute()
        folders = results.get('files', [])
        folder_id = folders[0]['id'] if folders else None

        if not folder_id:
            folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder['id']

        # Download file from Telegram
        doc = update.message.document
        tg_file = await doc.get_file()
        local_path = f"temp/{doc.file_name}"
        os.makedirs("temp", exist_ok=True)
        await tg_file.download_to_drive(local_path)

        # Upload to Google Drive
        file_metadata = {'name': doc.file_name, 'parents': [folder_id]}
        media = MediaFileUpload(local_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        os.remove(local_path)
        await update.message.reply_text("✅ File uploaded successfully to Google Drive.")
    except Exception as e:
        print(f"[Upload Error] {e}")
        await update.message.reply_text("❌ Upload failed. Try again.")

# Start Telegram bot
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("🚀 Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
