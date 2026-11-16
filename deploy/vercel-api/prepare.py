"""Assemble the Vercel API bundle in deploy/vercel-api/build/ (code only - the data is fetched at cold start).

    python deploy/vercel-api/prepare.py
    cd deploy/vercel-api/build && vercel deploy --prod
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "build"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "*.bak")

OUT.mkdir(exist_ok=True)
for item in OUT.iterdir():  # keep the .vercel project link, rebuild everything else
    if item.name != ".vercel":
        shutil.rmtree(item) if item.is_dir() else item.unlink()
shutil.copytree(ROOT / "backend", OUT / "backend", ignore=SKIP)
shutil.copytree(ROOT / "reports", OUT / "reports", ignore=shutil.ignore_patterns("*.md", "*.png", "*.html"))
# Vercel resets file times; keep the real report generation times for the engineering charts
mtimes = {p.relative_to(ROOT).as_posix(): p.stat().st_mtime for p in (ROOT / "reports").rglob("*") if p.is_file()}
(OUT / "reports" / "_mtimes.json").write_text(json.dumps(mtimes), encoding="utf-8")
shutil.copy2(ROOT / "frontend/public/assets/editions.json", OUT / "backend/api/editions.json")
shutil.copytree(HERE / "api", OUT / "api", ignore=SKIP)
for f in ("requirements.txt", "vercel.json", ".vercelignore"):
    shutil.copy2(HERE / f, OUT / f)
size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
print(f"bundle ready: {OUT} ({size / 1e6:.1f} MB of source)")
