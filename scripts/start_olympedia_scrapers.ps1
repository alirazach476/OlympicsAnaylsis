# Opens 2 visible PowerShell windows (Winter + Summer) that scrape Olympedia politely (Olympedia rate-limits 4+ parallel windows with HTTP 429).
# Safe to re-run any time (after reboot/crash): finished events are skipped, HTML is cached on disk.
# Run from the project folder:  .\scripts\start_olympedia_scrapers.ps1
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\.venv\Scripts\python.exe"
$groups = [ordered]@{
  'WINTER' = '--winter-only'
  'SUMMER' = '--summer-only'
}
foreach ($k in $groups.Keys) {
  $cmd = "`$Host.UI.RawUI.WindowTitle='Olympedia $k'; cd '$root'; & '$py' scripts/scrape_olympedia_results.py --no-db --delay 1.0 --no-skip-done $($groups[$k]); Write-Host 'FINISHED $k'"
  Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmd
}
