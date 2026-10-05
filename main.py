import json

from fetching_data.espn import ESPN
from fetching_data.nhl_api import fetch_all_teams_schedule
from fetching_data.nhl_api import fetch_standings
from db.nhl_db import insert_schedule_records
from db.dbclient import query


def main():
    print(json.dumps(fetch_standings(), indent=4))


if __name__ == "__main__":
    main()
