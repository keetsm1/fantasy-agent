import json
from datetime import datetime, timedelta, timezone

from api.client import COOKIES, get_espn, my_team_id, post_espn_transaction


class ESPN:
    def fetch_trade_proposals(self):
        """Return pending trade proposals involving this team's players."""
        data = get_espn(views=["mPendingTransactions"])
        proposals = []
        for transaction in data.get("pendingTransactions", []):
            items = transaction.get("items", [])
            is_pending = transaction.get("isPending") or transaction.get("status") == "PENDING"
            involves_my_team = any(
                item.get("type") == "TRADE"
                and my_team_id in (item.get("fromTeamId"), item.get("toTeamId"))
                for item in items
            )
            if is_pending and involves_my_team:
                proposals.append(transaction)
        return proposals

    def _current_scoring_period_id(self):
        data = get_espn(views=["mStatus"])
        status = data.get("status", {})
        period_id = (
            status.get("currentMatchupPeriod")
            or data.get("scoringPeriodId")
            or status.get("latestScoringPeriod")
            or status.get("currentScoringPeriod")
        )
        if isinstance(period_id, dict):
            period_id = period_id.get("id")
        if period_id is None:
            raise RuntimeError("ESPN did not return the current scoring period")
        return period_id

    def _submit_transaction(self, transaction_type, items=None, **extra):
        payload = {
            "type": transaction_type,
            "executionType": "EXECUTE",
            "teamId": my_team_id,
            "scoringPeriodId": self._current_scoring_period_id(),
            "isLeagueManager": False,
            "isActingAsTeamOwner": False,
            "skipTransactionCounters": False,
        }
        if COOKIES.get("swid"):
            payload["memberId"] = COOKIES["swid"]
        if items is not None:
            payload["items"] = items
        payload.update(extra)
        return post_espn_transaction(payload)

    def _get_incoming_trade_proposal(self, transaction_id):
        for proposal in self.fetch_trade_proposals():
            if str(proposal.get("id")) != str(transaction_id):
                continue
            if proposal.get("teamId") == my_team_id:
                continue
            if any(
                item.get("type") == "TRADE"
                and item.get("toTeamId") == my_team_id
                for item in proposal.get("items", [])
            ):
                return proposal
        raise ValueError("No pending incoming trade proposal found with that ID")

    def accept_trade(self, transaction_id):
        """Accept a pending trade proposal addressed to this team."""
        self._get_incoming_trade_proposal(transaction_id)
        return self._submit_transaction(
            "TRADE_ACCEPT",
            relatedTransactionId=str(transaction_id),
        )

    def reject_trade(self, transaction_id, comment=None):
        """Reject a pending trade proposal addressed to this team."""
        self._get_incoming_trade_proposal(transaction_id)
        extra = {"comment": comment} if comment else {}
        return self._submit_transaction(
            "TRADE_DECLINE",
            relatedTransactionId=str(transaction_id),
            **extra,
        )

    def offer_trade(
        self,
        other_team_id,
        send_player_ids,
        receive_player_ids,
        comment=None,
        expiration_days=7,
    ):
        """Offer a trade, identifying players by ESPN player ID."""
        send_player_ids = list(send_player_ids)
        receive_player_ids = list(receive_player_ids)
        if other_team_id == my_team_id:
            raise ValueError("other_team_id must identify another team")
        if not send_player_ids or not receive_player_ids:
            raise ValueError("A trade must include players on both sides")
        if len(set(send_player_ids)) != len(send_player_ids):
            raise ValueError("send_player_ids contains duplicates")
        if len(set(receive_player_ids)) != len(receive_player_ids):
            raise ValueError("receive_player_ids contains duplicates")
        if expiration_days < 1:
            raise ValueError("expiration_days must be at least 1")

        items = [
            {
                "playerId": player_id,
                "type": "TRADE",
                "fromTeamId": my_team_id,
                "toTeamId": other_team_id,
            }
            for player_id in send_player_ids
        ] + [
            {
                "playerId": player_id,
                "type": "TRADE",
                "fromTeamId": other_team_id,
                "toTeamId": my_team_id,
            }
            for player_id in receive_player_ids
        ]
        expiration_date = (datetime.now(timezone.utc) + timedelta(days=expiration_days)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        extra = {"expirationDate": expiration_date}
        if comment:
            extra["comment"] = comment
        return self._submit_transaction("TRADE_PROPOSAL", items, **extra)

    def drop_player(self, player_id):
        """Drop a player from this team's roster."""
        return self._submit_transaction(
            "FREEAGENT",
            [{"playerId": player_id, "type": "DROP", "fromTeamId": my_team_id}],
        )

    def pick_up_player(self, player_id, on_waivers=False, bid_amount=0, drop_player_id=None):
        """Add a free agent or submit a waiver claim; optionally drop a player too."""
        if bid_amount < 0:
            raise ValueError("bid_amount cannot be negative")
        if not on_waivers and bid_amount:
            raise ValueError("bid_amount is only valid for a waiver claim")

        items = [{"playerId": player_id, "type": "ADD", "toTeamId": my_team_id}]
        if drop_player_id is not None:
            if drop_player_id == player_id:
                raise ValueError("Cannot add and drop the same player")
            items.append({
                "playerId": drop_player_id,
                "type": "DROP",
                "fromTeamId": my_team_id,
            })

        extra = {"bidAmount": bid_amount} if on_waivers else {}
        transaction_type = "WAIVER" if on_waivers else "FREEAGENT"
        return self._submit_transaction(transaction_type, items, **extra)

    @staticmethod
    def _format_matchup(matchup, team_names):
        home = matchup.get("home", {})
        away = matchup.get("away", {})

        return {
            "week": matchup.get("matchupPeriodId"),
            "home": {
                "team_id": home.get("teamId"),
                "team_name": team_names.get(home.get("teamId")),
                "points": home.get("totalPoints"),
            },
            "away": {
                "team_id": away.get("teamId"),
                "team_name": team_names.get(away.get("teamId")),
                "points": away.get("totalPoints"),
            },
            "winner": matchup.get("winner"),
        }

    def fetch_current_matchup(self):
        status_data = get_espn(views=["mStatus"])
        status = status_data.get("status", {})
        current_week = status.get("currentMatchupPeriod")

        if current_week is not None:
            return self.fetch_matchups(current_week)

        # Fall back to ESPN's current scoreboard if status omits the period.
        data = get_espn(views=["mTeam", "mScoreboard"])
        team_names = {
            team.get("id"): team.get("name")
            for team in data.get("teams", [])
        }
        return [
            self._format_matchup(matchup, team_names)
            for matchup in data.get("schedule", [])
        ]

    def fetch_my_matchup(self):
        for matchup in self.fetch_current_matchup():
            if my_team_id in (
                matchup["home"]["team_id"],
                matchup["away"]["team_id"],
            ):
                return matchup

        return None

    def fetch_matchups(self, week):
        data = get_espn(
            views=["mTeam", "mMatchupScore"],
            params={"matchupPeriodId": week},
        )
        team_names = {
            team.get("id"): team.get("name")
            for team in data.get("teams", [])
        }
        return [
            self._format_matchup(matchup, team_names)
            for matchup in data.get("schedule", [])
            if matchup.get("matchupPeriodId") == week
        ]

    def fetch_all_matchups(self):
        """Fetch the league's full season schedule across all matchup periods."""
        data = get_espn(views=["mTeam", "mSchedule"])
        team_names = {
            team.get("id"): team.get("name")
            for team in data.get("teams", [])
        }
        return [
            self._format_matchup(matchup, team_names)
            for matchup in data.get("schedule", [])
        ]

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

    def fetch_player_fantasy_points(self):
        """Return current-season fantasy totals for rostered players."""
        players = []
        for team in self.get_teams():
            roster = team.get("roster", {})
            for entry in roster.get("entries", []):
                pool_entry = entry.get("playerPoolEntry", {})
                player = pool_entry.get("player")
                if player is None:
                    continue

                players.append({
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "player_id": player.get("id"),
                    "player_name": player.get("fullName"),
                    "fantasy_points": pool_entry.get("appliedStatTotal"),
                    "player": player,
                    "roster_entry": entry,
                })

        return players

    def fetch_fantasy_rules(self):
        """Return the league's raw ESPN settings, including scoring rules."""
        data = get_espn(views=["mSettings"])
        return data.get("settings", {})

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
