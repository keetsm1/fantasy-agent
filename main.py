import json

from fetching_data.espn import ESPN


def _print_result(function_name, result):
    print(f"\n=== {function_name} ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    espn = ESPN()

    _print_result("get_teams()", espn.get_teams())
#    _print_result("get_players()", espn.get_players())
#    _print_result("fetch_my_team()", espn.fetch_my_team())
#    _print_result("available_players()", espn.available_players())


if __name__ == "__main__":
    main()
