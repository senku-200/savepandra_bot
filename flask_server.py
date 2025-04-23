from flask import Flask, request
from google_auth_oauthlib.flow import InstalledAppFlow
import threading

app = Flask(__name__)

# Store flow per user
user_flows = {}
credentials_event = threading.Event()

def set_user_flow(user_id, flow):
    user_flows[user_id] = flow
    credentials_event.clear()

@app.route("/oauth2callback")
def oauth_callback():
    # Get user ID from query param
    user_id = request.args.get("state")  # Passed via authorization_url as "state"

    if not user_id or user_id not in user_flows:
        return "❌ User flow not found. Please restart /start in Telegram."

    flow = user_flows[user_id]

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials_event.set()
        return "✅ Authorization successful. You may close this tab."
    except Exception as e:
        print(f"[OAuth Error] {e}")
        return "❌ Authorization failed. Please try again."
