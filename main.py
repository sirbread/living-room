import os
import random
import time
import threading
import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import logging
import asyncio

load_dotenv()
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

oauth_token = None
token_expiry = 0
cached_channels = []
last_update = 0
shared_channel = {"channel": None, "updated_at": time.time()}
session = requests.Session()

last_global_change = 0
GLOBAL_COOLDOWN = 3  #seconds

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
        logging.info(f"refreshed {len(cached_channels)} channels")
    except Exception as e:
        logging.error(f"failed to refresh channels: {e}")

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

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.last_change: dict[WebSocket, float] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.last_change[websocket] = 0
        logging.info(f"ws client connected. total: {len(self.active_connections)}")
        await self.broadcast_online_count()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.last_change:
            del self.last_change[websocket]
        logging.info(f"ws client disconnected. total: {len(self.active_connections)}")
        asyncio.create_task(self.broadcast_online_count())

    async def broadcast(self, message: dict):
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.warning(f"broadcast failed (removing client): {e}")
                to_remove.append(connection)
        for conn in to_remove:
            self.disconnect(conn)

    async def broadcast_online_count(self):
        await self.broadcast({"type": "update_online", "online": len(self.active_connections)})

    def can_change(self, websocket, cooldown=3):
        now = time.time()
        if now - self.last_change.get(websocket, 0) > cooldown:
            self.last_change[websocket] = now
            return True
        return False

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global last_global_change
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "sync", "channel": shared_channel["channel"]})
        while True:
            try:
                data = await websocket.receive_json()
            except Exception as e:
                break
            if data.get("type") == "change_channel":
                now = time.time()
                #fist do a global cooldown check
                if now - last_global_change < GLOBAL_COOLDOWN:
                    continue
                #then do a user cooldown check
                if not manager.can_change(websocket):
                    await websocket.send_json({
                        "type": "error",
                        "message": "slow down! you're changing channels too fast."
                    })
                    continue

                channel = get_random_live_channel()
                if channel:
                    shared_channel["channel"] = channel
                    shared_channel["updated_at"] = now
                    last_global_change = now
                    await manager.broadcast({"type": "sync", "channel": channel})
                    await manager.broadcast({"type": "global_cooldown"})
                    logging.info(f"channel changed to {channel}")
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "no streams available."
                    })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"ws error: {e}")
    finally:
        manager.disconnect(websocket)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not shared_channel["channel"]:
        shared_channel["channel"] = get_random_live_channel()
    return templates.TemplateResponse("index.html", {"request": request, "channel_name": shared_channel["channel"] or ""})

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/stats")
async def stats():
    return {
        "connections": len(manager.active_connections),
        "last_channel": shared_channel["channel"],
        "last_update": shared_channel["updated_at"]
    }