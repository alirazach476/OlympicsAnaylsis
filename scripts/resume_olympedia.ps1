# Resume Olympedia scrape after reboot / crash.
# Safe to re-run: skips event pages already saved under data/raw/olympedia/editions/
# GPU is NOT used — this is network scraping; GPU cannot speed it up.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Resuming Olympedia scrape from disk checkpoints..."
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
$env:DATABASE_URL = "sqlite+pysqlite:///./data/olympics_warehouse.db"

# 1) Load any match JSON written since last DB sync
python scripts/load_olympedia_fixtures.py

# 2) Continue Winter then Summer (single stream = fewer HTTP 429s)
#    Cached events are skipped instantly.
python scripts/scrape_olympedia_results.py --winter-only --no-db --delay 1.2
python scripts/scrape_olympedia_results.py --summer-only --no-db --delay 1.2

# 3) Final DB sync
python scripts/load_olympedia_fixtures.py
python scripts/load_olympedia_sports_catalog.py

Write-Host "Done. Checkpoint: data\raw\olympedia\checkpoint.json"
