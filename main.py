from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
    video_id = get_random_video_id() or "idFWFoZIgbQ"
    return templates.TemplateResponse("index.html", {"request": request, "video_id": video_id})

@app.get("/random")
def random_video():
    video_id = get_random_video_id()
    if video_id:
        return JSONResponse(content={"video_id": video_id})
    return JSONResponse(content={"error": "no streams available"}, status_code=404)
