import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
DB = ROOT / "tracker.sqlite3"
KEY = os.getenv("RIOT_API_KEY", "").strip()
GAME = os.getenv("RIOT_GAME_NAME", "Âsk")
TAG = os.getenv("RIOT_TAG_LINE", "ice")
PLATFORM = os.getenv("RIOT_PLATFORM", "tr1").lower()
REGION = os.getenv("RIOT_REGION", "europe").lower()
POLL = max(60, int(os.getenv("POLL_SECONDS", "90")))
LOOKBACK = max(5, min(50, int(os.getenv("MATCH_LOOKBACK", "20"))))
SCOPE = os.getenv("MATCH_SCOPE", "solo").lower()
if SCOPE not in ("solo", "ranked"):
    SCOPE = "solo"
state_lock = threading.Lock()
state = {"mode": "demo", "name": GAME + "#" + TAG, "rank": None,
         "matches": [], "season_win_rate": None, "match_scope": SCOPE,
         "session": {"wins": 0, "losses": 0, "lp_delta": None},
         "updated": None, "error": None}
_puuid = None

def db():
    c = sqlite3.connect(DB, timeout=10)
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS seen_matches(id TEXT PRIMARY KEY,ended_ms INTEGER,win INTEGER,champion TEXT,kills INTEGER,deaths INTEGER,assists INTEGER,duration INTEGER,queue_id INTEGER DEFAULT 0)")
    cols = {r[1] for r in c.execute("PRAGMA table_info(seen_matches)")}
    if "queue_id" not in cols:
        c.execute("ALTER TABLE seen_matches ADD COLUMN queue_id INTEGER DEFAULT 0")
    c.commit()
    return c

def setting(c, key, default=""):
    r = c.execute("SELECT v FROM settings WHERE k=?", (key,)).fetchone()
    return r[0] if r else default

def save_setting(c, key, value):
    c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key,str(value)))

def riot(host, path, params=None):
    try:
        r = requests.get(f"https://{host}.api.riotgames.com{path}", headers={"X-Riot-Token":KEY}, params=params, timeout=15)
    except requests.RequestException as e:
        raise RuntimeError("Riot connection failed: " + str(e)) from e
    if r.status_code == 429:
        raise RuntimeError("Riot API rate limit reached")
    if r.status_code in (401,403):
        raise RuntimeError("Riot API key expired or unauthorized")
    if r.status_code == 404:
        raise RuntimeError("Riot account or requested resource not found")
    r.raise_for_status()
    return r.json()

def puuid():
    global _puuid
    if _puuid is None:
        data = riot(REGION, "/riot/account/v1/accounts/by-riot-id/" + quote(GAME,safe="") + "/" + quote(TAG,safe=""))
        _puuid = data["puuid"]
    return _puuid

def get_rank(p):
    entries = riot(PLATFORM, "/lol/league/v4/entries/by-puuid/" + quote(p,safe=""))
    e = next((item for item in entries if item.get("queueType") == "RANKED_SOLO_5x5"), None)
    if not e:
        return None
    return {"tier":e["tier"], "division":e["rank"], "lp":int(e["leaguePoints"]),
            "wins":int(e["wins"]), "losses":int(e["losses"])}

def get_matches(p):
    path = "/lol/match/v5/matches/by-puuid/" + quote(p,safe="") + "/ids"
    ids = riot(REGION, path, {"start":0,"count":LOOKBACK,"queue":420})
    if SCOPE == "ranked":
        ids += riot(REGION, path, {"start":0,"count":LOOKBACK,"queue":440})
    ids = list(dict.fromkeys(ids))
    c = db()
    errors = 0
    try:
        for mid in ids:
            if c.execute("SELECT 1 FROM seen_matches WHERE id=?", (mid,)).fetchone():
                continue
            try:
                match = riot(REGION, "/lol/match/v5/matches/" + quote(mid,safe=""))
            except RuntimeError as e:
                if "rate limit" in str(e).lower() or "expired" in str(e).lower():
                    raise
                errors += 1
                continue
            info = match.get("info") or {}
            q = int(info.get("queueId") or 0)
            if q not in ((420,440) if SCOPE == "ranked" else (420,)):
                continue
            player = next((v for v in info.get("participants",[]) if v.get("puuid")==p),None)
            if not player:
                continue
            dur = int(info.get("gameDuration") or 0)
            ended = int(info.get("gameEndTimestamp") or (int(info.get("gameStartTimestamp") or info.get("gameCreation") or 0) + dur*1000))
            if not ended:
                continue
            c.execute("INSERT OR IGNORE INTO seen_matches VALUES(?,?,?,?,?,?,?,?,?)",
                      (mid,ended,int(bool(player.get("win"))),player.get("championName") or "?",
                       int(player.get("kills") or 0),int(player.get("deaths") or 0),
                       int(player.get("assists") or 0),dur,q))
            c.commit()
        where = "queue_id IN (420,440)" if SCOPE=="ranked" else "queue_id=420"
        rows = c.execute("SELECT id,ended_ms,win,champion,kills,deaths,assists,duration,queue_id FROM seen_matches WHERE "+where+" ORDER BY ended_ms DESC LIMIT 5").fetchall()
        return [{"id":r[0],"ended_ms":r[1],"win":bool(r[2]),"champion":r[3],
                 "k":r[4],"d":r[5],"a":r[6],"duration":r[7]//60,
                 "queue":"FLEX" if r[8]==440 else "SOLO"} for r in rows],errors
    finally:
        c.close()

def refresh():
    p = puuid()
    rank = get_rank(p)
    matches, failures = get_matches(p)
    c = db()
    try:
        now = int(time.time())
        start = int(setting(c,"session_start","0"))
        if not start:
            start = now
            save_setting(c,"session_start",start)
        base = setting(c,"baseline")
        if rank and not base:
            base = f'{rank["tier"]}|{rank["division"]}|{rank["lp"]}'
            save_setting(c,"baseline",base)
        delta = None
        if rank and base:
            try:
                t,d,l = base.split("|")
                if (t,d)==(rank["tier"],rank["division"]):
                    delta=rank["lp"]-int(l)
            except ValueError:
                pass
        queue_sql = "queue_id IN (420,440)" if SCOPE=="ranked" else "queue_id=420"
        w,l = c.execute("SELECT COALESCE(SUM(CASE WHEN win=1 THEN 1 ELSE 0 END),0),COALESCE(SUM(CASE WHEN win=0 THEN 1 ELSE 0 END),0) FROM seen_matches WHERE ended_ms>=? AND "+queue_sql,(start*1000,)).fetchone()
        c.commit()
    finally:
        c.close()
    total = (rank["wins"]+rank["losses"]) if rank else 0
    with state_lock:
        state.update(mode="live",rank=rank,matches=matches,
            season_win_rate=round(rank["wins"]*100/total) if total else None,
            session={"wins":w,"losses":l,"lp_delta":delta},
            updated=datetime.now(timezone.utc).isoformat(),
            error=f"{failures} match details unavailable" if failures else None)

def worker():
    while True:
        if KEY and not KEY.startswith("RGAPI_BURAYA"):
            try:
                refresh()
            except Exception as e:
                with state_lock:
                    state["error"]=str(e)
                    state["mode"]="stale" if state["updated"] else "error"
        time.sleep(POLL)

@app.get("/")
def home():
    return render_template("overlay.html",dashboard=True)

@app.get("/overlay")
def overlay():
    return render_template("overlay.html",dashboard=False)

@app.get("/api/state")
def get_state():
    with state_lock:
        return jsonify(dict(state))

@app.post("/api/session/reset")
def reset_session():
    if request.remote_addr not in ("127.0.0.1","::1"):
        return jsonify(error="local only"),403
    with state_lock:
        rank=state["rank"]
        state["session"]={"wins":0,"losses":0,"lp_delta":0 if rank else None}
    c=db()
    try:
        save_setting(c,"session_start",int(time.time()))
        save_setting(c,"baseline",f'{rank["tier"]}|{rank["division"]}|{rank["lp"]}' if rank else "")
        c.commit()
    finally:
        c.close()
    return jsonify(ok=True)

if __name__=="__main__":
    db().close()
    threading.Thread(target=worker,daemon=True).start()
    app.run(host="127.0.0.1",port=8000,debug=False,threaded=True)
