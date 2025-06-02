import requests
import sqlite3
import time
import random
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get('aypeeiykie')
db_path = 'streams.db'
timestamp_path = 'last_run.txt'
one_hour = 3600 #i live for these variables

keywords = [
    'live',
    'gaming',
    'music',
    'news',
    'sports',
    'chill',
    'talk show',
    'education',
    'travel',
    'technology'
]

def search_live_streams(query, max_results=25):
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {
        'part': 'snippet',
        'q': query,
        'eventType': 'live',
        'type': 'video',
        'maxResults': max_results,
        'key': api_key
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return [item['id']['videoId'] for item in r.json().get('items', [])]

def check_embeddable(video_id):
    url = 'https://www.googleapis.com/youtube/v3/videos'
    params = {
        'part': 'player',
        'id': video_id,
        'key': api_key
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    items = r.json().get('items', [])
    if not items:
        return False
    return 'embedHtml' in items[0].get('player', {})

def save_to_db(video_id, fresh=False):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('create table if not exists live_streams (video_id text unique)')
    if fresh:
        c.execute('delete from live_streams')
    c.execute('insert or ignore into live_streams (video_id) values (?)', (video_id,))
    conn.commit()
    conn.close()

def main():
    now = time.time()
    fresh = True

    if os.path.exists(timestamp_path):
        try:
            with open(timestamp_path, 'r') as f:
                last_run = float(f.read().strip())
                if now - last_run < one_hour:
                    fresh = False
        except:
            pass

    keyword = random.choice(keywords)
    print(f"searching key word (live): {keyword!r}")

    video_ids = search_live_streams(keyword, max_results=50)
    print(f"found {len(video_ids)} live streams for '{keyword}'")

    added = 0
    wiped = False

    for vid in video_ids:
        if check_embeddable(vid):
            if fresh and not wiped:
                save_to_db(vid, fresh=True)
                wiped = True
            else:
                save_to_db(vid)
            print(f"saved: {vid}")
            added += 1
        else:
            print(f"fuck you, these ones arent embeddable: {vid}")
        time.sleep(0.4)

    print(f"{added} embeddable streams saved")

    with open(timestamp_path, 'w') as f:
        f.write(str(now))

if __name__ == '__main__':
    main()

