import os
import requests
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

