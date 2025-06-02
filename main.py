from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import random

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = "streams.db"

def get_random_video_id():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT video_id FROM live_streams ORDER BY RANDOM() LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = sqlite3.connect("streams.db")
    cursor = conn.cursor()
    cursor.execute("SELECT video_id FROM live_streams ORDER BY RANDOM() LIMIT 1")
    result = cursor.fetchone()
    conn.close()

    video_id = result[0] if result else "idFWFoZIgbQ"  
    return templates.TemplateResponse("index.html", {"request": request, "video_id": video_id})
