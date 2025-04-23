from flask import Flask, request
from google_auth_oauthlib.flow import InstalledAppFlow
import threading

app = Flask(__name__)

flow = None
credentials_event = threading.Event()  # Thread-safe signal

@app.route("/oauth2callback")
def oauth_callback():
    global flow
    if not flow:
        return "❌ OAuth flow not set. Please restart the bot."

    code = request.args.get("code")
    if code:
        try:
            flow.fetch_token(code=code)
            credentials_event.set()
            return "✅ Authorization successful. You may close this tab."
        except Exception as e:
            print(f"[OAuth Error] {e}")
            return "❌ Authorization failed. Please try again."
    return "❌ No authorization code found."

def set_flow(oauth_flow):
    global flow
    flow = oauth_flow
    credentials_event.clear()

def run_flask_server():
    app.run(port=8080, debug=False, use_reloader=False)
