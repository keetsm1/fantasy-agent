from concurrent.futures import ThreadPoolExecutor
import requests
from fetching_data.player_mapping import NHL_TEAMS

BASE_URL = "https://api-web.nhle.com/v1"


def fetch_schedule_per_team(team_abbrev: str, season: str = "20262027") -> dict:
    """Fetches the season schedule payload for a specific NHL team."""
    url = f"{BASE_URL}/club-schedule-season/{team_abbrev}/{season}"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    return res.json()


def fetch_all_teams_schedule(season: str = "20262027") -> list[dict]:
    """
    Fetches season schedules concurrently across all 32 NHL teams
    and returns a combined list of raw game objects.
    """
    all_games = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda team: fetch_schedule_per_team(team, season), NHL_TEAMS))

    for data in results:
        all_games.extend(data.get("games", []))

    return all_games