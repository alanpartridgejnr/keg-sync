# FPL Draft Data Sync

Automatically pulls data from the Fantasy Premier League Draft API
(`draft.premierleague.com`) on a schedule and commits it to this repo as
JSON, so it's always available at a stable public URL — including for
Claude, which can fetch files under `raw.githubusercontent.com` directly.

## Setup

1. Create a new **public** GitHub repo (private repos work too, but then
   the raw file URLs require an auth token to fetch, which defeats the
   "just curl it" convenience).
2. Copy these files into it, preserving the folder structure:
   - `.github/workflows/refresh-fpl-data.yml`
   - `scripts/fetch_fpl_data.py`
3. Edit `LEAGUE_ID` in `.github/workflows/refresh-fpl-data.yml` if your
   league ID isn't `2605`.
4. Push to GitHub. The workflow runs automatically every 6 hours, or you
   can trigger it immediately from the repo's **Actions** tab → "Refresh
   FPL Draft data" → **Run workflow**.
5. After the first run, you'll have a `data/` folder with:
   - `bootstrap-static.json` — all players, teams, positions
   - `league-details.json` — standings, all H2H matches, managers
   - `element-status.json` — current player ownership snapshot
   - `transactions.json` — waiver/free-agent/trade history

## Getting the data into a Claude conversation

Once it's live, the raw files sit at predictable URLs, e.g.:

```
https://raw.githubusercontent.com/{your-username}/{repo-name}/main/data/bootstrap-static.json
```

Give me (Claude) that URL directly in a message — because you provided
the link, I'm able to fetch it, so you won't need to re-paste the JSON
every time. Just say "pull the latest data from [url]" and I'll fetch
the current version.

## Adjusting the schedule

The default is every 6 hours. During a draft or right around gameweek
deadlines you may want it more frequent — edit the `cron` line in the
workflow file. Cron schedules are in UTC.

## Optional: full roster history

Set `FETCH_PICKS: "true"` in the workflow's `env` block to also pull
every manager's picks for every gameweek into `data/all-picks.json`.
This is off by default because it's ~380 requests per run (10 managers
× 38 gameweeks) — fine for a one-off backfill, unnecessary to repeat
every 6 hours once the season's history is captured. Consider running
it once with picks enabled, then switching back to `"false"` for
ongoing syncs of just the frequently-changing files.
