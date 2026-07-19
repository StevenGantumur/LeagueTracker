from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/matches")
def matches():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        SELECT match_id, champion_id, kills, deaths, assists, 
                 total_minions_killed, gold_earned, win
        FROM participants
        WHERE puuid = %s
        ORDER BY match_id DESC
        LIMIT 20
    """, (os.getenv("PUUID"),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    columns = ["match_id", "champion_id", "kills", "deaths", "assists", "total_minions_killed", "gold_earned", "win"]
    return [dict(zip(columns, row)) for row in rows]