import requests
import os
import json
# For pagination
import time
import psycopg2

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
PUUID = os.getenv("PUUID")

def riotGet(url, params=None):
    for attempt in range(3):
        response = requests.get(url, headers={"X-Riot-Token": API_KEY}, params=params)

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 15))
            print(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/3)")
            time.sleep(wait)
            continue
        
        response.raise_for_status()
        return response.json()
    
    raise requests.exceptions.RequestException(f"Failed to get {url} after 3 attempts")



def getMatchIds(puuid, count=20, start=0):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"count": count, "queue": 420, "start": start}  # 420 = ranked solo/duo
    response = riotGet(url, params=params)
    return response

def getMatchDetails(matchId):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{matchId}"
    return riotGet(url)


def getMatchTimeline(matchId):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{matchId}/timeline"
    return riotGet(url)
        
def matchToRow(detail):
      info = detail["info"]
      metadata = detail["metadata"]

      match_id = metadata["matchId"]
      game_creation = info["gameCreation"]
      game_duration = info["gameDuration"]
      game_version = info["gameVersion"]
      queue_id = info["queueId"]
      winning_team_id = None
      for team in info["teams"]:
        if team["win"]:
          winning_team_id = team["teamId"]
          break

      return (match_id, game_creation, game_duration, game_version, queue_id, winning_team_id)

def participantsToRows(detail):
      match_id = detail["metadata"]["matchId"]
      rows = []
      for p in detail["info"]["participants"]:
          rows.append((
              match_id,
              p["puuid"],
              p["teamId"],
              p["teamPosition"],
              p["championId"],
              p["kills"],
              p["deaths"],
              p["assists"],
              p["goldEarned"],
              p["totalMinionsKilled"],
              p["neutralMinionsKilled"],
              p["totalDamageDealtToChampions"],
              p["visionScore"],
              p["wardsPlaced"],
              p["wardsKilled"],
              p["turretTakedowns"],
              p["win"],
          ))
      return rows

def timelinesToRows(timeline):
    match_id = timeline["metadata"]["matchId"]
    id_to_puuid = {p["participantId"]: p["puuid"] for p in timeline["info"]["participants"]}

    rows = []
    for frame in timeline["info"]["frames"]:
        minute = frame["timestamp"] // 60000
        for pid_str, pframe in frame["participantFrames"].items():
            puuid = id_to_puuid[int(pid_str)]
            rows.append((
                match_id, puuid, minute,
                pframe["totalGold"],
                pframe["minionsKilled"],
                pframe["jungleMinionsKilled"],
                pframe["level"],
                pframe["xp"]
            ))
    return rows

def getAllMatchIds(puuid, target =200):
    all_ids = []
    start = 0
    while len(all_ids) < target:
        page = getMatchIds(puuid, count=100, start=start)
        if not page:
            break
        all_ids.extend(page)
        start+= 100
        time.sleep(1.3)
    return all_ids[:target]
def main():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    cur.execute("SELECT match_id FROM matches")
    existing = {row[0] for row in cur.fetchall()}
    
    matchIds = getAllMatchIds(PUUID, target=200)
    print(f"Got {len(matchIds)} match IDs")

    for matchId in matchIds:
        if matchId in existing:
            continue  
        try:
            detail = getMatchDetails(matchId)
            if detail["info"]["participants"][0]["gameEndedInSurrender"]:
                print(f"Skipping remake {matchId}")
            timeline = getMatchTimeline(matchId)
            
            cur.execute(
                "INSERT INTO matches (match_id, game_creation, game_duration, game_version, queue_id, winning_team_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (match_id) DO NOTHING",
                matchToRow(detail)
            )   
            cur.executemany(
                "INSERT INTO participants ("
                "  match_id, puuid, team_id, team_position, champion_id, "
                "  kills, deaths, assists, gold_earned, total_minions_killed, "
                "  neutral_minions_killed, total_damage_dealt_to_champions, "
                "  vision_score, wards_placed, wards_killed, turret_takedowns, win"
                ") VALUES ("
                "  %s, %s, %s, %s, %s, "
                "  %s, %s, %s, %s, %s, "
                "  %s, %s, %s, %s, %s, %s, %s"
                ") ON CONFLICT (match_id, puuid) DO NOTHING",
                participantsToRows(detail)
            )

            cur.executemany(
                "INSERT INTO participant_timelines ("
                "  match_id, puuid, minute, total_gold, minions, jungle_cs, level, xp"
                ") VALUES ("
                "  %s, %s, %s, %s, %s, %s, %s, %s"
                ") ON CONFLICT (match_id, puuid, minute) DO NOTHING",
                timelinesToRows(timeline)
            ) 

            conn.commit()
            print(f"Processed {matchId}")
            
        except requests.exceptions.RequestException:
            print(f"Error fetching details for {matchId}, skipping")
        finally: 
            time.sleep(2.5)                                          
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

