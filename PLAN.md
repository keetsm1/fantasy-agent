# Fantasy Hockey Agent: Implementation Plan

This document outlines the architecture, the functions to create, their specific purposes, and the step-by-step implementation order—without code blocks.

---

## System Architecture & Workflow

1. **ESPN Data Source**: Fetches your team's roster, league H2H Points rules, current matchup scores, trade offers, and available free agents.
2. **NHL Data Source**: Fetches real-world game schedules, season stats, ice time, and recent 5-game trends from official NHL endpoints.
3. **Database Layer (Neon Postgres)**: Caches the mapping between ESPN player IDs and NHL player IDs so player data can be joined accurately without redundant lookups.
4. **Analytics Layer**: Translates NHL stats into fantasy point values using your league's scoring rules, and counts upcoming games remaining in the matchup period.
5. **Agent Tools & Decision Loop**: Exposes high-level data functions to an AI agent to analyze strengths, weaknesses, waiver targets, and trade options.
6. **Human-in-the-Loop Guard**: Prompts the user for confirmation before executing any add, drop, or trade on ESPN.

---

## Modules and Functions Overview

### 1. Database & Persistence (`db/dbclient.py`)
- **`query(sql, params, fetch)`**
  - **Purpose**: Executes parameterized SQL queries against Postgres.
  - **Key Change**: Update the database connection to fall back to the `neondb` environment variable if `DATABASE_URL` is not set.
- **`init_db()`**
  - **Purpose**: Creates the `player_mapping` table in Neon Postgres to store matched ESPN and NHL player IDs, full names, teams, positions, and match statuses (`MATCHED`, `AMBIGUOUS`, `NOT_FOUND`).

---

### 2. Player Identity Resolution (`fetching_data/player_mapper.py`)
Because ESPN and NHL use completely different numeric IDs for players, this module resolves and verifies identities before stats are combined.

- **`PlayerMapper.get_nhl_id(espn_player)`**
  - **Inputs**: ESPN player dictionary containing ID and full name.
  - **Outputs**: A tuple containing the NHL player ID (or None) and a status string (`MATCHED`, `AMBIGUOUS`, `NOT_FOUND`).
  - **Purpose**:
    1. Checks the in-memory cache and Postgres `player_mapping` table.
    2. If not found, queries the NHL Search API with the player's name.
    3. Filters search results for active NHL players matching the exact name.
    4. If exactly one active match exists, records the NHL ID and marks as `MATCHED`.
    5. If multiple active players share the name, marks as `AMBIGUOUS` so the agent will alert the user instead of hallucinating.
    6. Saves the result to Postgres for future lookups.
- **`PlayerMapper._save_mapping(espn_id, nhl_id, name, team, position, status)`**
  - **Purpose**: Internal helper that executes an upsert query to save or update the mapping record in Postgres.

---

### 3. NHL API Client (`api/client.py` and `fetching_data/nhl_api.py`)

#### HTTP Helper (`api/client.py`)
- **`get_nhl(path, params)`**
  - **Purpose**: Makes authenticated or public GET requests to `https://api-web.nhle.com/v1`, handles timeouts, verifies HTTP status codes, and returns parsed JSON.

#### NHL Fetcher Class (`fetching_data/nhl_api.py`)
- **`NHL_API.fetch_schedule(date)`**
  - **Purpose**: Retrieves the NHL game schedule for a specific date or the current week to show which teams play on each day.
- **`NHL_API.fetch_team_schedule(team_abbr)`**
  - **Purpose**: Fetches the season schedule for an individual NHL team. Used to determine how many games that team has left in the active fantasy matchup period.
- **`NHL_API.fetch_player_profile(nhl_id)`**
  - **Purpose**: Queries the NHL player landing endpoint. Extracts regular season totals (goals, assists, points, shots, plus-minus, power-play points) and trims the last 5 games into a lightweight summary (ice time, points, shots, opponent).
- **`NHL_API.fetch_player_game_log(nhl_id, season, game_type)`**
  - **Purpose**: Retrieves full game-by-game logs for a player across an entire season to evaluate multi-week streaks or slump patterns.
- **`NHL_API.fetch_standings()`**
  - **Purpose**: Retrieves current league standings, goal differentials, and win/loss records to provide strength-of-schedule context.
- **`NHL_API.fetch_scoreboard(date)`**
  - **Purpose**: Pulls live in-progress and final game scores for today's games.

---

### 4. League Analytics Engine (`analysis/`)

#### Scoring Evaluator (`analysis/scoring.py`)
- **`ScoringEvaluator.estimate_points(stats_dict)`**
  - **Purpose**: Takes a dictionary of skater stats and calculates expected fantasy points using your league's exact H2H Points weights:
    - Goals: 5.0
    - Assists: 3.75
    - Game Winning Goals: 5.0
    - Short Handed Points: 4.0
    - Power Play Points: 1.0
    - Hits: 0.7
    - Blocks: 0.5
    - Shots on Goal: 0.4
    - Plus/Minus: 0.4
    - Penalty Minutes: -0.2
- **`ScoringEvaluator.get_rule_summary()`**
  - **Purpose**: Formats the active league scoring rules into a clean text summary that can be fed into the agent's prompt.

#### Schedule Analyzer (`analysis/schedule_analyzer.py`)
- **`ScheduleAnalyzer.get_remaining_games_this_week(team_abbr, end_of_week_date)`**
  - **Purpose**: Scans a team's upcoming schedule and returns the number of games scheduled between today and the end of the current fantasy matchup period.
- **`ScheduleAnalyzer.has_back_to_back(team_abbr, date_range)`**
  - **Purpose**: Identifies back-to-back game days within a matchup period, which is critical for evaluating backup goalie starts and potential skater fatigue.

---

### 5. Agent Tools & Decision Layer (`agent/`)

#### High-Level Tools (`agent/tools.py`)
- **`AgentTools.get_roster_summary()`**
  - **Purpose**: Combines ESPN roster entries with their mapped NHL profiles, current fantasy totals, injury statuses, recent 5-game performance, and remaining games this week.
- **`AgentTools.get_matchup_summary()`**
  - **Purpose**: Pulls current matchup scores for both teams, compares remaining games across both rosters, and highlights point deficits or leads.
- **`AgentTools.get_waiver_recommendations(limit)`**
  - **Purpose**: Pulls top available free agents from ESPN, joins their NHL recent performance and upcoming schedule, and filters for high-upside pickup candidates.
- **`AgentTools.compare_players(player_names)`**
  - **Purpose**: Performs a side-by-side comparison between two or more players (ice time trends, power-play time, scoring rate, upcoming games).
- **`AgentTools.evaluate_trade_offer(transaction_id)`**
  - **Purpose**: Analyzes an incoming or pending trade proposal by comparing the expected fantasy output and schedule impact of players being sent vs. received.

#### Transaction Guard (`agent/guard.py`)
- **`TransactionGuard.confirm_action(action_type, details)`**
  - **Purpose**: Displays the exact proposed transaction (e.g. Add Player A, Drop Player B) in the terminal and requires an explicit `[y/N]` confirmation from the user before executing the transaction on ESPN.

#### Agent Engine (`agent/agent.py`)
- **`FantasyAgent.analyze_team()`**
  - **Purpose**: Synthesizes roster health, upcoming game volume, and matchup score to generate a prioritized plan for the week.
- **`FantasyAgent.recommend_waiver_moves()`**
  - **Purpose**: Identifies the weakest droppable roster spots and recommends waiver wire replacements with clear reasoning tied to schedule and scoring rules.
- **`FantasyAgent.evaluate_trades()`**
  - **Purpose**: Reviews pending trade proposals and recommends whether to accept, reject, or negotiate.

---

### 6. Interactive Command-Line Interface (`main.py`)
- **`main()`**
  - **Purpose**: Provides a menu or CLI interface supporting:
    1. Team briefing (view roster, health, games remaining).
    2. Current matchup briefing (score, opponent, games remaining).
    3. Waiver wire search with AI recommendations.
    4. Trade analysis.
    5. Safe transaction execution (guarded by confirmation prompts).

---

## Step-by-Step Implementation Roadmap

1. **Step 1: Database Setup**
   - In `db/dbclient.py`, add support for the `neondb` environment variable.
   - Define and run `init_db()` to create the `player_mapping` table in Neon Postgres.

2. **Step 2: Player Identity Resolver**
   - Create `fetching_data/player_mapper.py`.
   - Implement name querying against the NHL Search API.
   - Implement caching and conflict resolution in the Postgres database.

3. **Step 3: NHL Data Fetching**
   - In `api/client.py`, add the `get_nhl` function.
   - In `fetching_data/nhl_api.py`, implement methods for schedule, team schedule, player landing page, game logs, and standings.
   - Ensure player profile responses extract only the necessary stats to keep data compact.

4. **Step 4: League Analytics**
   - Create `analysis/scoring.py` to calculate projected fantasy points based on your league's H2H Points multiplier table.
   - Create `analysis/schedule_analyzer.py` to count remaining games for any team in the active matchup week.

5. **Step 5: Agent Tools & Guard**
   - Create `agent/tools.py` to stitch ESPN data, NHL stats, schedules, and mapping together.
   - Create `agent/guard.py` to enforce interactive user confirmation before any ESPN write call.
   - Create `agent/agent.py` to run the reasoning loop and formulate recommendations.

6. **Step 6: CLI Runner**
   - Update `main.py` with commands to run the briefing, evaluate waivers, inspect matchups, and execute approved roster moves.
