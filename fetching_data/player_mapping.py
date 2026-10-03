import unicodedata
import re
import requests
from fetching_data.espn import fetch_all_players

BASE_URL = "https://api-web.nhle.com/v1/"

# Map ESPN's numeric proTeamId to official NHL 3-letter abbreviations
ESPN_PRO_TEAM_MAP = {
    1: "BOS", 2: "BUF", 3: "CGY", 4: "CHI", 5: "DET", 6: "EDM",
    7: "CAR", 8: "LAK", 9: "DAL", 10: "MTL", 11: "NJD", 12: "NYI",
    13: "NYR", 14: "OTT", 15: "PHI", 16: "PIT", 17: "COL", 18: "SJS",
    19: "STL", 20: "TBL", 21: "TOR", 22: "VAN", 23: "WSH", 25: "ANA",
    26: "FLA", 27: "NSH", 28: "WPG", 29: "CBJ", 30: "MIN", 37: "VGK",
    124292: "SEA", 129764: "UTA"
}
NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
    "WPG", "WSH"
]

# Map ESPN position IDs (1: C, 2: LW, 3: RW, 4: D, 5: G)
ESPN_POS_MAP = {1: "C", 2: "L", 3: "R", 4: "D", 5: "G"}
    
def normalize_name(text: str) -> str:
    """Strip accents, special characters, and lowercase."""
    if not text:
        return ""
    # Decompose unicode (e.g., è -> e + `) and drop combining characters
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return " ".join(text.lower().split())

def build_nhl_catalogue()-> list[dict]:
    catalogue = []

    for team in NHL_TEAMS:
        res = requests.get(f"{BASE_URL}/roster/{team}/current")

        if res.status_code != 200:
            continue

        data = res.json()

    for group in ["forwards", "defensemen", "goalies"]:
        for p in data.get(group, []):
            full_name = f"{p['firstName']['default']} {p['lastName']['default']}"
            catalogue.append({
                "nhl_id": str(p["id"]),
                "player_name": full_name,
                "norm_name": normalize_name(full_name),
                "team_code": team,
                "position": p.get("positionCode")
                })

    return catalogue

def map_to_espn(espn_player:dict, nhl_catalogue: list[dict]):
    #1. match by name -> if more than 1 match -> map by team abbrev -> if more than 1 match map by pos
    #    def fetch_all_players(self, page_size=1000, save_path=None):


