from db.dbclient import execute_many


def insert_schedule_records(games: list[dict]) -> int:
    records = []
    seen_game_ids = set()

    for game in games:
        # Only regular season (gameType == 2)
        if game.get("gameType") != 2:
            continue

        game_id = game["id"]
        if game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)

        home = game.get("homeTeam", {})
        away = game.get("awayTeam", {})

        records.append((
            game_id,
            game.get("season"),
            game.get("gameDate"),
            home.get("abbrev"),
            away.get("abbrev"),
            home.get("score"),
            away.get("score"),
            game.get("gameState"),
        ))

    if not records:
        return 0

    sql = """
    INSERT INTO nhl_schedule (
        game_id,
        season,
        game_date,
        home_team,
        away_team,
        home_score,
        away_score,
        game_state
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_id) DO UPDATE
    SET home_score = EXCLUDED.home_score,
        away_score = EXCLUDED.away_score,
        game_state = EXCLUDED.game_state,
        game_date = EXCLUDED.game_date;
    """

    execute_many(sql, records)

    return len(records)