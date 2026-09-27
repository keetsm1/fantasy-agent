import json

from api.client import get_espn, my_team_id


class ESPN:
    def get_teams(self):
        league = get_espn(views=["mTeam", "mRoster"])
        return league.get("teams", [])

    def get_players(self):
        players = []
        for team in self.get_teams():
            roster = team.get("roster", {})
            for entry in roster.get("entries", []):
                player = entry.get("playerPoolEntry", {}).get("player")
                if player is not None:
                    players.append({
                        "team_id": team.get("id"),
                        "team_name": team.get("name"),
                        "player": player,
                        "roster_entry": entry,
                    })

        return players

    def fetch_my_team(self):
        teams = self.get_teams()
        for team in teams:
            if team.get("id") == my_team_id:
                return team

        return None

    def available_players(self, page_size=100):
        if page_size < 1:
            raise ValueError("page_size must be at least 1")

        players = []
        offset = 0

        while True:
            fantasy_filter = {
                "players": {
                    "filterStatus": {
                        "value": ["FREEAGENT", "WAIVERS"]
                    },
                    "limit": page_size,
                    "offset": offset,
                    "sortPercOwned": {
                        "sortPriority": 1,
                        "sortAsc": False,
                    },
                }
            }

            data = get_espn(
                views=["kona_player_info"],
                headers={"X-Fantasy-Filter": json.dumps(fantasy_filter)},
            )
            batch = data.get("players", [])
            players.extend(batch)
            if len(batch) < page_size:
                break
            offset += len(batch)

        return players
