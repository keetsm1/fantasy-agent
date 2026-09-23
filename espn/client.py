import os

import requests
from dotenv import load_dotenv

load_dotenv()

league_id = os.getenv("LEAGUE_ID")
year = 2027

cookies ={
    "espn_s2": os.getenv("ESPN_S2") ,
    "swid": os.getenv("ESPN_SWID")
}

url = ( os.getenv("LEAGUE_API_URL"))

params = [
    ("view", "mTeam"),
    ("view", "mRoster"),
    ("view", "mMatchup"),
    ("view", "mSettings"),
    ("view", "mStandings"),
]

response = requests.get(url, params=params, cookies=cookies, timeout=30)
response.raise_for_status()
data = response.json()

for team in data.get("teams", []):
    team_name = (
        team.get("name")
        or " ".join(part for part in (team.get("location"), team.get("nickname")) if part)
        or team.get("teamName")
        or f"Team {team.get('id', 'unknown')}"
    )
    print(f"\n{team_name}")

    entries = team.get("roster", {}).get("entries", [])
    if not entries:
        print("  (no roster entries returned)")
        continue

    for entry in entries:
        player = entry.get("playerPoolEntry", {}).get("player", entry.get("player", {}))
        player_name = player.get("fullName") or player.get("firstName", "") + " " + player.get("lastName", "")
        print(f"  {player_name.strip() or 'Unknown player'}")
