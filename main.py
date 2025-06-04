import os
import random
import time
import threading
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

oauth_token = None
token_expiry = 0
cached_channels = []
last_update = 0
session = requests.Session()

def get_twitch_oauth_token():
    global oauth_token, token_expiry
    if oauth_token and time.time() < token_expiry - 60:
        return oauth_token
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    resp = session.post(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    oauth_token = data["access_token"]
    token_expiry = time.time() + data["expires_in"]
    return oauth_token

def refresh_channels():
    global cached_channels, last_update
    try:
        token = get_twitch_oauth_token()
        url = "https://api.twitch.tv/helix/streams"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        }

        channels = []
        cursor = None
        for _ in range(10):  #a thousand streams, in case this thing does go viral (smh)
            params = {"first": 100}
            if cursor:
                params["after"] = cursor
            resp = session.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            channels += data.get("data", [])
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

        cached_channels = [c["user_login"] for c in channels if "user_login" in c]
        last_update = time.time()
        print(f"Refreshed {len(cached_channels)} channels")
    except Exception as e:
        print("Failed to refresh channels:", e)

def periodic_refresh():
    while True:
        if time.time() - last_update > 300: 
            refresh_channels()
        time.sleep(60)

threading.Thread(target=periodic_refresh, daemon=True).start()

def get_random_live_channel():
    if cached_channels:
        return random.choice(cached_channels)
    else:
        return None

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    channel_name = get_random_live_channel()
    return templates.TemplateResponse("index.html", {"request": request, "channel_name": channel_name or ""})

@app.get("/random")
def random_stream():
    channel_name = get_random_live_channel()
    if not channel_name:
        return JSONResponse(content={"error": "no streams available"}, status_code=404)
    return JSONResponse(content={"channel_name": channel_name})