from api.client import get_espn

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
            if team.get(id) == 8:
                return team

        return None

    def free_agents_available(self):
        players = []
        data = get_espn(views= ["kona_player_info"])