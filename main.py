import json

from fetching_data.espn import ESPN
from fetching_data.nhl_api import fetch_all_teams_schedule
from db.nhl_db import insert_schedule_records
from db.dbclient import query


def _print_result(function_name, result):
    print(f"\n=== {function_name} ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    all_games = fetch_all_teams_schedule()

    count = insert_schedule_records(all_games)


if __name__ == "__main__":
    main()
