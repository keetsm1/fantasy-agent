from concurrent.futures import ThreadPoolExecutor
import requests
from fetching_data.player_mapping import NHL_TEAMS

BASE_URL = "https://api-web.nhle.com/v1"


def fetch_schedule_per_team(team_abbrev: str, season: str = "20262027") -> dict:
    url = f"{BASE_URL}/club-schedule-season/{team_abbrev}/{season}"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    return res.json()


def fetch_all_teams_schedule(season: str = "20262027") -> list[dict]:
    all_games = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda team: fetch_schedule_per_team(team, season), NHL_TEAMS))

    for data in results:
        all_games.extend(data.get("games", []))

    return all_games

def fetch_player_stats(player_nhl_id: int):
    URL = f"{BASE_URL}/player/{player_nhl_id}/landing"

    res = requests.get(URL, timeout = 10)
    data = res.json()

    featured = data.get("featuredStats", {})
    sub_season = featured.get("regularSeason", {}).get("subSeason", {})

    season_stats = {
        "season": featured.get("season"),
        "games_played": sub_season.get("gamesPlayed", 0),
        "goals": sub_season.get("goals", 0),
        "assists": sub_season.get("assists", 0),
        "points": sub_season.get("points", 0),
        "plus_minus": sub_season.get("plusMinus", 0),
        "pim": sub_season.get("pim", 0),
        "shots": sub_season.get("shots", 0),
        "shooting_pctg": sub_season.get("shootingPctg", 0.0),
        "power_play_goals": sub_season.get("powerPlayGoals", 0),
        "power_play_points": sub_season.get("powerPlayPoints", 0),
        "shorthanded_goals": sub_season.get("shorthandedGoals", 0),
        "shorthanded_points": sub_season.get("shorthandedPoints", 0),
        "game_winning_goals": sub_season.get("gameWinningGoals", 0),
        "ot_goals": sub_season.get("otGoals", 0),
    }

    return season_stats

def fetch_last_5_games(player_nhl_id:int):
    URL = f"{BASE_URL}/player/{player_nhl_id}/landing"
    
    res = requests.get(URL, timeout = 10)
    data = res.json()

    recent_games = data.get("last5Games", [])

    stats = []

    for game in recent_games:
        stats.append(
            {
                "game_id": game.get("gameId"),
                "date": game.get("gameDate"),
                "opponent": game.get("opponentAbbrev"),
                "goals": game.get("goals"),
                "assists": game.get("assists"),
                "points": game.get("points"),
                "plus_minus": game.get("plusMinus"),
                "shots": game.get("shots"),
                "toi": game.get("toi"),  # Time on ice (MM:SS)
            }
        )
    return stats


def fetch_standings() -> list[dict]:
    url = f"{BASE_URL}/standings/now"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()

    cleaned_standings = []
    for team in data.get("standings", []):
        streak_code = team.get("streakCode", "")
        streak_count = team.get("streakCount", "")
        streak = f"{streak_code}{streak_count}" if streak_code else "N/A"

        l10_w = team.get("l10Wins", 0)
        l10_l = team.get("l10Losses", 0)
        l10_ot = team.get("l10OtLosses", 0)

        cleaned_standings.append({
            "team_abbrev": team.get("teamAbbrev", {}).get("default"),
            "team_name": team.get("teamName", {}).get("default"),
            "division": team.get("divisionName"),
            "conference": team.get("conferenceName"),
            "games_played": team.get("gamesPlayed", 0),
            "wins": team.get("wins", 0),
            "losses": team.get("losses", 0),
            "ot_losses": team.get("otLosses", 0),
            "points": team.get("points", 0),
            "point_pctg": round(team.get("pointPctg", 0.0), 3),
            "goals_for": team.get("goalFor", 0),
            "goals_against": team.get("goalAgainst", 0),
            "goal_differential": team.get("goalDifferential", 0),
            "streak": streak,
            "l10_record": f"{l10_w}-{l10_l}-{l10_ot}",
            "division_rank": team.get("divisionSequence"),
            "league_rank": team.get("leagueSequence"),
        })

    return cleaned_standings