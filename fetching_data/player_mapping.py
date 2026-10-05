import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor
import requests
from fetching_data.espn import fetch_all_players
from db.dbclient import execute_many, query

BASE_URL = "https://api-web.nhle.com/v1"
SEARCH_URL = "https://search.d3.nhle.com/api/v1/search/player"


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
    
FIRST_NAME_ALIASES = {
    "sam": "samuel", "zack": "zachary", "zach": "zachary",
    "joe": "joseph", "josh": "joshua", "max": "maxwell",
    "alex": "alexander", "mitch": "mitchell", "matt": "matthew",
    "nick": "nicholas", "dan": "daniel", "dave": "david",
    "chris": "christopher", "tom": "thomas", "mike": "michael",
    "tony": "anthony", "cam": "cameron", "cal": "callan",
    "will": "william", "rob": "robert", "bob": "robert"
}
    
def normalize_name(text: str) -> str:
    """Strip accents, special characters, middle initials, expand nicknames, and lowercase."""
    if not text:
        return ""
    # Decompose unicode (e.g., è -> e + `) and drop combining characters
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    tokens = text.lower().split()
    # Strip isolated single-letter middle initials (e.g., 'elias n pettersson' -> 'elias pettersson')
    tokens = [t for t in tokens if len(t) > 1]
    # Expand first name aliases
    if tokens and tokens[0] in FIRST_NAME_ALIASES:
        tokens[0] = FIRST_NAME_ALIASES[tokens[0]]
    return " ".join(tokens)


def build_nhl_catalogue() -> list[dict]:
    catalogue = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
    }

    with requests.Session() as session:
        session.headers.update(headers)
        for team in NHL_TEAMS:
            res = session.get(f"{BASE_URL}/roster/{team}/current")

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
            time.sleep(0.05)

    return catalogue

def map_to_espn(espn_player: dict, nhl_catalogue: list[dict]) -> dict | None:
    """
    Map an ESPN player to their corresponding entry in the NHL catalogue.

    Resolution logic:
    1. Match by normalized name.
    2. If multiple matches, disambiguate by NHL team abbreviation.
    3. If still multiple matches, disambiguate by position code (C, L, R, D, G).
    """
    player_info = espn_player.get("player") if isinstance(espn_player.get("player"), dict) else espn_player

    # Extract and normalize name
    raw_name = (
        player_info.get("name")
        or player_info.get("fullName")
        or player_info.get("player_name")
        or ""
    )
    espn_norm = player_info.get("norm_name") or normalize_name(raw_name)
    if not espn_norm:
        return None

    # Step 1: Match by normalized name
    matches = [
        p for p in nhl_catalogue
        if (p.get("norm_name") or normalize_name(p.get("player_name", ""))) == espn_norm
    ]

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # Step 2: Disambiguate by team abbreviation if more than 1 match
    espn_team = player_info.get("team") or player_info.get("team_code")
    if not espn_team and "proTeamId" in player_info:
        espn_team = ESPN_PRO_TEAM_MAP.get(player_info.get("proTeamId"))

    if espn_team and espn_team != "FA":
        team_matches = [p for p in matches if p.get("team_code") == espn_team]
        if len(team_matches) == 1:
            return team_matches[0]
        elif len(team_matches) > 1:
            matches = team_matches

    # Step 3: Disambiguate by position if more than 1 match
    espn_pos = player_info.get("pos") or player_info.get("position")
    if not espn_pos and "defaultPositionId" in player_info:
        espn_pos = ESPN_POS_MAP.get(player_info.get("defaultPositionId"))

    if espn_pos:
        pos_str = str(espn_pos).upper()
        if pos_str == "LW":
            pos_str = "L"
        elif pos_str == "RW":
            pos_str = "R"

        pos_matches = [
            p for p in matches
            if str(p.get("position", "")).upper() in (
                pos_str,
                "LW" if pos_str == "L" else ("RW" if pos_str == "R" else pos_str)
            )
        ]
        if len(pos_matches) == 1:
            return pos_matches[0]
        elif len(pos_matches) > 1:
            matches = pos_matches

    if len(matches) == 1:
        return matches[0]

    return None


def search_nhl_player(espn_player: dict, session: requests.Session | None = None) -> dict | None:
    """
    Search the NHL official player search API for free agents, unsigned players,
    and players not found in the current active team rosters.
    """
    player_info = espn_player.get("player") if isinstance(espn_player.get("player"), dict) else espn_player
    raw_name = (
        player_info.get("name")
        or player_info.get("fullName")
        or player_info.get("player_name")
        or ""
    )
    norm_target = normalize_name(raw_name)
    if not norm_target:
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
    }

    url = f"{SEARCH_URL}?culture=en-us&limit=15&q={raw_name}"
    try:
        requester = session if session is not None else requests
        res = requester.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return None
        hits = res.json()
    except Exception:
        return None

    # Filter for exact normalized name match
    exact = [h for h in hits if normalize_name(h.get("name", "")) == norm_target]
    if not exact:
        return None

    if len(exact) == 1:
        hit = exact[0]
        return {
            "nhl_id": str(hit["playerId"]),
            "player_name": hit.get("name"),
            "norm_name": norm_target,
            "team_code": hit.get("teamAbbrev") or hit.get("lastTeamAbbrev"),
            "position": hit.get("positionCode"),
        }

    # If multiple matches, disambiguate by position
    espn_pos = player_info.get("pos") or player_info.get("position")
    if not espn_pos and "defaultPositionId" in player_info:
        espn_pos = ESPN_POS_MAP.get(player_info.get("defaultPositionId"))

    if espn_pos:
        pos_str = str(espn_pos).upper()
        if pos_str in ("LW", "RW"):
            pos_str = "L" if pos_str == "LW" else "R"
        pos_matches = [h for h in exact if h.get("positionCode") == pos_str]
        if len(pos_matches) == 1:
            hit = pos_matches[0]
            return {
                "nhl_id": str(hit["playerId"]),
                "player_name": hit.get("name"),
                "norm_name": norm_target,
                "team_code": hit.get("teamAbbrev") or hit.get("lastTeamAbbrev"),
                "position": hit.get("positionCode"),
            }

    # If multiple matches, disambiguate by team / lastTeam
    espn_team = player_info.get("team") or player_info.get("team_code")
    if not espn_team and "proTeamId" in player_info:
        espn_team = ESPN_PRO_TEAM_MAP.get(player_info.get("proTeamId"))

    if espn_team and espn_team != "FA":
        team_matches = [
            h for h in exact
            if h.get("teamAbbrev") == espn_team or h.get("lastTeamAbbrev") == espn_team
        ]
        if len(team_matches) == 1:
            hit = team_matches[0]
            return {
                "nhl_id": str(hit["playerId"]),
                "player_name": hit.get("name"),
                "norm_name": norm_target,
                "team_code": hit.get("teamAbbrev") or hit.get("lastTeamAbbrev"),
                "position": hit.get("positionCode"),
            }

    return None


def insert_player_mappings(records: list[tuple[str, str, str]]) -> int:
    """
    Inserts a list of (espn_id, nhl_id, player_name) tuples into the player_mapping table.
    Uses ON CONFLICT (espn_id) DO UPDATE to handle existing records.
    Returns the number of records inserted/updated.
    """
    if not records:
        return 0

    sql = """
        INSERT INTO player_mapping (espn_id, nhl_id, player_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (espn_id) DO UPDATE
        SET nhl_id = EXCLUDED.nhl_id,
            player_name = EXCLUDED.player_name;
    """
    execute_many(sql, records)
    return len(records)


def populate_player_mapping_table(include_fas: bool = True) -> int:
    """
    Builds the NHL catalogue, fetches ESPN players, maps active roster players,
    and uses the NHL search API to map Free Agents (FAs) and non-roster players.
    Inserts all resolved player identities into the player_mapping database table.
    Returns the total count of mapped players saved to the database.
    """
    print("Building NHL catalogue across all 32 teams...")
    catalogue = build_nhl_catalogue()
    print(f"Loaded {len(catalogue)} active players into NHL catalogue.")

    print("Fetching ESPN players...")
    espn_players = fetch_all_players(page_size=1000)
    print(f"Fetched {len(espn_players)} ESPN players.")

    seen_nhl_ids = set()
    seen_espn_ids = set()
    records = []
    unmapped_espn = []

    # Phase 1: Fast local mapping against active NHL roster catalogue
    for ep in espn_players:
        nhl_p = map_to_espn(ep, catalogue)
        if nhl_p:
            nhl_id = str(nhl_p["nhl_id"])
            espn_id = str(ep.get("id") or (ep.get("player") or {}).get("id"))
            if nhl_id not in seen_nhl_ids and espn_id not in seen_espn_ids:
                seen_nhl_ids.add(nhl_id)
                seen_espn_ids.add(espn_id)
                records.append((espn_id, nhl_id, nhl_p["player_name"]))
        else:
            unmapped_espn.append(ep)

    print(f"Phase 1 (Active Rosters): Mapped {len(records)} players.")

    # Phase 2: Resolve Free Agents (FAs) and remaining players via NHL Search API
    if include_fas and unmapped_espn:
        print(f"Phase 2 (Free Agents & Non-Roster): Searching NHL database for {len(unmapped_espn)} players...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            search_results = list(executor.map(search_nhl_player, unmapped_espn))

        fa_matched = 0
        for ep, nhl_p in zip(unmapped_espn, search_results):
            if nhl_p:
                nhl_id = str(nhl_p["nhl_id"])
                espn_id = str(ep.get("id") or (ep.get("player") or {}).get("id"))
                if nhl_id not in seen_nhl_ids and espn_id not in seen_espn_ids:
                    seen_nhl_ids.add(nhl_id)
                    seen_espn_ids.add(espn_id)
                    records.append((espn_id, nhl_id, nhl_p["player_name"]))
                    fa_matched += 1

        print(f"Phase 2: Mapped an additional {fa_matched} Free Agents / non-roster players.")

    print(f"Total mapped players: {len(records)}. Inserting into Neon Postgres...")
    count = insert_player_mappings(records)
    print(f"Successfully populated player_mapping table with {count} players in Neon Postgres.")
    return count


if __name__ == "__main__":
    populate_player_mapping_table()