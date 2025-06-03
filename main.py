import os
import random
import time
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
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    oauth_token = data["access_token"]
    token_expiry = time.time() + data["expires_in"]
    return oauth_token

def get_random_live_channel():
    token = get_twitch_oauth_token()
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }
    params = {"first": 100}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return None
    channel = random.choice(data)
    return channel["user_login"]

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