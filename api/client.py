import os
import requests
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv
load_dotenv()

my_team_id = 8
league_id = os.getenv("LEAGUE_ID")
year = 2027
BASE_URL = ( os.getenv("LEAGUE_API_URL"))
COOKIES ={
    "espn_s2": os.getenv("ESPN_S2") ,
    "swid": os.getenv("ESPN_SWID")
}

def get_espn(views = None , params = None, headers = None  ):
    query = []

    if views : 
        for view in views:
            query.append(("view", view))


    if params:
        for key,value in params.items():
            query.append((key,value))

    response = requests.get(
    BASE_URL,
    params=query,
    cookies=COOKIES,
    headers=headers,
    )

    response.raise_for_status()

    return response.json()


def post_espn_transaction(payload):
    """Submit a league transaction to ESPN's write endpoint."""
    if not BASE_URL:
        raise RuntimeError("LEAGUE_API_URL is not configured")

    parsed_url = urlsplit(BASE_URL)
    host = parsed_url.netloc.replace(
        "lm-api-reads.fantasy.espn.com",
        "lm-api-writes.fantasy.espn.com",
    )
    if host == parsed_url.netloc and "fantasy.espn.com" in host:
        host = "lm-api-writes.fantasy.espn.com"

    write_url = os.getenv("LEAGUE_WRITE_API_URL")
    if not write_url:
        path = parsed_url.path.rstrip("/") + "/transactions/"
        write_url = urlunsplit((parsed_url.scheme, host, path, "", ""))
    elif not write_url.rstrip("/").endswith("/transactions"):
        write_url = write_url.rstrip("/") + "/transactions/"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-fantasy-platform": "espn-fantasy-web",
        "x-fantasy-source": "kona",
    }
    response = requests.post(
        write_url,
        json=payload,
        cookies=COOKIES,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    if not response.content:
        return {"submitted": True, "status_code": response.status_code}
    try:
        return response.json()
    except ValueError:
        return {
            "submitted": True,
            "status_code": response.status_code,
            "response_text": response.text,
        }
