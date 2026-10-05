import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("neondb")

def query(sql, params = None, fetch = False):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            cur.execute(sql, params)

            if fetch:
                return cur.fetchall()

def execute_many(sql, params_seq):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params_seq)
