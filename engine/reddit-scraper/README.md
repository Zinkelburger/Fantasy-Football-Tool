# Reddit Scraper — per-player draft notes

Scrapes r/fantasyfootball (plus saved FF Hound articles) for discussion of each
draftable player, filters it down to high-confidence mentions, and has an LLM
summarize each player into a markdown note used by the draft tool.

Past seasons' final notes live in `../2024/analysis/` and `../2025/go/analysis/`.
The intermediate scraped text (`raw_data/`, `filtered_data/`, `ff-hound/`,
`markdown_data/`) is **gitignored on purpose** — see `API-TOS.md`: scraped Reddit
comments can't be republished, and this repo is public. Only the generated
summaries get committed.

## Pipeline

```
combined_with_depth.csv          player list: name, team, pos, ADP, depth, nickname
        │
        ▼
main_scrape_reddit_api.py        PRAW search of r/fantasyfootball, tiered name
        │                        matching (full name / nickname = high confidence,
        │                        unique last name = medium, shared last name = low)
        ▼
filtered_data/<slug>_reddit_discussion.txt     (+ <slug>_processing_metadata.json)
        │
        ▼
process_ff_hound.py              greps saved FF Hound HTML (ff-hound/*.html)
        │                        for player mentions
        ▼
filtered_data/<slug>_ff_hound_discussion.txt
        │
        ▼
combine_analyses.py              merges the two per player
        │
        ▼
filtered_data/<slug>_final_discussion.txt
        │
        ▼
live_process.py                  one API call per player (or submit_batch.py /
        │                        get_batch_results.py for the 50%-cheaper Batch API)
        ▼
markdown_data/<Player Name>.md   final note per player
```

`run_full_analysis.py` runs the first three steps in order. `workflow.py` is a
menu-driven wrapper around the batch scripts. The summarizers prefer
`_final_discussion.txt` and fall back to `_reddit_discussion.txt` if the
combine step wasn't run. Shared naming/prompt logic lives in `pipeline_utils.py`.

Every step is resumable: already-produced output files are skipped, so a
crashed run can just be restarted.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp docs/example-.env .env   # then fill in real values
```

`.env` needs (see `docs/example-.env`):

- `CLIENT_ID` / `CLIENT_SECRET` — Reddit script app from https://www.reddit.com/prefs/apps
- `USER_AGENT` — any descriptive string
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, live summarizer; default `gpt-5-nano-2025-08-07`)
- `OPENAI_BATCH_MODEL` (optional, batch summarizer; default `gpt-5-mini`)

## Each season's checklist

1. Download the FantasyPros overall-ADP export **and** the six JuiceBoxOne
   per-platform ranking CSVs (ESPN/Sleeper × Standard/Half PPR/PPR — this is
   where the draft tool's ESPN and Sleeper comparison columns come from, and
   what makes the three scoring formats differ). Then:
   `python build_player_csv.py FantasyPros_<year>_Overall_ADP_Rankings.csv --juicebox <dir>`
   This regenerates `combined_with_depth.csv` (nicknames carry over) and the
   three `../go/*_with_depth.csv` board files. Without `--juicebox` the boards
   still build, but ESPN_Rank is blank and all three formats are identical —
   `go test ./...` fails on `TestRankVariationExists` until the data is supplied.
2. Save current FF Hound sleeper/bust articles as HTML into `ff-hound/`
   (optional — the pipeline runs Reddit-only without it).
3. `python run_full_analysis.py` — the scrape takes hours; it's resumable.
4. `python live_process.py` — or `submit_batch.py` then `get_batch_results.py`
   (up to 24h turnaround).
5. Copy `markdown_data/` into the year's analysis directory for the draft tool.

The season year in prompts and Reddit search queries is derived from the
current date (`pipeline_utils.current_season_year()`), so nothing needs
editing year to year.

## Notes

- `main.py` is the legacy first-pass scraper, superseded by
  `main_scrape_reddit_api.py`. Kept for reference.
- Ideas for next season: `TODO-2026.md`.
- Caveat from the 2025 backtest (`../reddit-notes-study/`): note *tone* added no
  draft edge over ADP, and hyped players mildly underperformed. Treat these notes
  as qualitative context (injury/situation flags), not a ranking signal.
