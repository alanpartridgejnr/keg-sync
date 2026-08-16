#!/usr/bin/env python3
"""
Fetches Fantasy Premier League Draft data and saves it as JSON files
in the data/ directory, for a scheduled GitHub Actions job to commit.

Usage:
    python scripts/fetch_fpl_data.py

Environment variables:
    LEAGUE_ID       - your draft league ID (required)
    START_EVENT     - first gameweek to pull entry picks for (default: 1)
    END_EVENT       - last gameweek to pull entry picks for (default: 38)
    FETCH_PICKS     - "true"/"false", whether to also pull every manager's
                       picks for every gameweek (default: "false", since
                       it's a lot of requests and rarely needs refreshing
                       for past/finished gameweeks)
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://draft.premierleague.com/api"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEAGUE_ID = os.environ.get("LEAGUE_ID", "12932")
START_EVENT = int(os.environ.get("START_EVENT", "1"))
END_EVENT = int(os.environ.get("END_EVENT", "38"))
FETCH_PICKS = os.environ.get("FETCH_PICKS", "false").lower() == "true"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fpl-draft-sync/1.0)",
    "Accept": "application/json",
}


def fetch_json(url: str, retries: int = 3, delay: float = 1.5):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def save_json(filename: str, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Saved {path} ({path.stat().st_size:,} bytes)")


def get_latest_finished_event(bootstrap: dict) -> int:
    """Returns the highest gameweek number that has finished, or 0 if none have.
    Falls back safely to 0 if the events data isn't in the expected shape."""
    events = bootstrap.get("events", [])
    if not isinstance(events, list):
        print(f"Warning: unexpected 'events' type ({type(events).__name__}); skipping gameweek cap.")
        return 0

    finished_ids = []
    for e in events:
        if isinstance(e, dict) and e.get("finished"):
            gw_id = e.get("id")
            if isinstance(gw_id, int):
                finished_ids.append(gw_id)

    if not finished_ids and events:
        print(f"Warning: 'events' present but no finished gameweeks found. Sample item: {events[0]!r}")

    return max(finished_ids) if finished_ids else 0


def main():
    print(f"Fetching FPL Draft data for league {LEAGUE_ID}...")

    # 1. Player/team master data — the main thing that needs regular refreshing
    bootstrap = fetch_json(f"{BASE_URL}/bootstrap-static")
    save_json("bootstrap-static.json", bootstrap)

    # 2. League details — standings, matches, managers
    league_details = fetch_json(f"{BASE_URL}/league/{LEAGUE_ID}/details")
    save_json("league-details.json", league_details)

    # 3. Current player ownership (rostered / waivers / free agents)
    element_status = fetch_json(f"{BASE_URL}/league/{LEAGUE_ID}/element-status")
    save_json("element-status.json", element_status)

    # 3.5. Original draft picks (who drafted which player, in what order)
    try:
        draft_choices = fetch_json(f"{BASE_URL}/draft/{LEAGUE_ID}/choices")
        save_json("draft-choices.json", draft_choices)
    except RuntimeError as e:
        print(f"Warning: could not fetch draft choices ({e}); skipping.")

    # 4. Waiver/free-agent/trade transactions
    try:
        transactions = fetch_json(f"{BASE_URL}/draft/league/{LEAGUE_ID}/transactions")
        save_json("transactions.json", transactions)
    except RuntimeError as e:
        print(f"Warning: could not fetch transactions ({e}); skipping.")

    # 5. (Optional) every manager's picks for every gameweek
    if FETCH_PICKS:
        # Cap END_EVENT at the latest finished gameweek so we don't waste
        # time and retries hitting 404s for gameweeks that haven't happened yet.
        latest_finished = get_latest_finished_event(bootstrap)
        effective_end = min(END_EVENT, latest_finished) if latest_finished else 0

        if effective_end < START_EVENT:
            print(f"No finished gameweeks yet (latest finished: {latest_finished}); skipping picks fetch.")
        else:
            print(f"Fetching picks for gameweeks {START_EVENT}-{effective_end} (latest finished: {latest_finished})")
            entry_ids = [e["entry_id"] for e in league_details.get("league_entries", [])]
            all_picks = {}
            for entry_id in entry_ids:
                all_picks[str(entry_id)] = {}
                for event in range(START_EVENT, effective_end + 1):
                    url = f"{BASE_URL}/entry/{entry_id}/event/{event}"
                    try:
                        picks = fetch_json(url)
                        all_picks[str(entry_id)][str(event)] = picks
                    except RuntimeError as e:
                        print(f"Warning: entry {entry_id} GW{event} failed ({e})")
                    time.sleep(0.3)  # be polite to the API
            save_json("picks-history.json", all_picks)

    print("Done.")


if __name__ == "__main__":
    main()
