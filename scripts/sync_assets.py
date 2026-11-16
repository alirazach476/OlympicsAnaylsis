#!/usr/bin/env python3
"""Index the user-supplied Olympic assets, publish web copies to frontend/public/assets and register them in the `assets` table.

* "Olympics Editions Logo/<summer olympics|olympics winter> YYYY[ background].<ext>"  -> edition logo / background for that Games
* data/pictograms/Olympics <Summer|Winter> YYYY/*                                     -> sport pictograms of that Games
Licence/attribution are NOT guessed: rows are marked 'user-supplied (licence not verified)'. Re-runnable; originals are never modified.
"""
import json, re, shutil, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "frontend" / "public" / "assets"
con = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
con.execute("PRAGMA busy_timeout=300000")
games = {r[0] for r in con.execute("SELECT games_id FROM games")}
IMG = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".avif", ".gif")
manifest = {"logos": {}, "backgrounds": {}, "pictograms": {}, "mascots": {}}
rows = []


def add(gid, kind, title, src: Path, dest_rel: str):
    d = PUB / dest_rel
    d.parent.mkdir(parents=True, exist_ok=True)
    if not d.exists() or d.stat().st_size != src.stat().st_size:
        shutil.copyfile(src, d)
    w = h = None
    rows.append((gid, kind, title, str(src.relative_to(ROOT)).replace("\\", "/"), f"/assets/{dest_rel}"))


logo_dir = ROOT / "Olympics Editions Logo"
for f in sorted(logo_dir.glob("*")) if logo_dir.exists() else []:
    m = re.match(r"(?:(summer) olympics|olympics (winter)) (\d{4})( background)?\.(\w+)$", f.name, re.I)
    if not m or f.suffix.lower() not in IMG:
        continue
    season = (m.group(1) or m.group(2)).lower()
    gid = f"{m.group(3)}_{season}"
    if gid not in games:
        continue
    bg = bool(m.group(4))
    rel = f"{'backgrounds' if bg else 'logos'}/{gid}{f.suffix.lower()}"
    add(gid, "edition_background" if bg else "edition_logo", f"{season.title()} {m.group(3)} {'background' if bg else 'logo'}", f, rel)
    manifest["backgrounds" if bg else "logos"][gid] = f"/assets/{rel}"

pic_root = ROOT / "data" / "pictograms"
for d in sorted(pic_root.glob("Olympics *")) if pic_root.exists() else []:
    m = re.match(r"Olympics (Summer|Winter) (\d{4})$", d.name)
    if not m:
        continue
    gid = f"{m.group(2)}_{m.group(1).lower()}"
    for f in sorted(d.glob("*")):
        if f.suffix.lower() in IMG and not f.name.lower().startswith("screenshot"):
            rel = f"pictograms/{gid}/{f.name}"
            add(gid, "sport_pictogram", f.stem, f, rel)
            manifest["pictograms"].setdefault(gid, []).append(f"/assets/{rel}")

# mascots/<summer|winter> YYYY.<ext> or mascots/YYYY <summer|winter>.<ext>  -> mascot image for that Games
for f in sorted((ROOT / "mascots").glob("*")) if (ROOT / "mascots").exists() else []:
    m = re.match(r"(?:(summer|winter) (\d{4})|(\d{4}) (summer|winter))\.(\w+)$", f.name, re.I)
    if not m or f.suffix.lower() not in IMG:
        continue
    season = (m.group(1) or m.group(4)).lower(); year = m.group(2) or m.group(3)
    gid = f"{year}_{season}"
    if gid not in games:
        continue
    rel = f"mascots/{gid}{f.suffix.lower()}"
    add(gid, "mascot", f"{season.title()} {year} mascot", f, rel)
    manifest["mascots"][gid] = f"/assets/{rel}"

con.execute("DELETE FROM assets WHERE license LIKE 'user-supplied%'")
con.executemany("INSERT INTO assets(games_id,asset_type,title,local_path,remote_url,license,attribution,description,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))",
                [(g, k, t, p, u, "user-supplied (licence not verified)", "not recorded - verify before redistribution", "indexed by scripts/sync_assets.py", "unverified") for g, k, t, p, u in rows])
con.commit()
(PUB / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
(PUB / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
missing = sorted(g for g in games if re.match(r"(19[6-9]\d|20[0-2]\d)", g) and g not in manifest["logos"])
print(f"logos {len(manifest['logos'])}, backgrounds {len(manifest['backgrounds'])}, pictogram Games {len(manifest['pictograms'])} ({sum(map(len, manifest['pictograms'].values()))} files)")
print("Games without a logo:", missing)

# mascots table: one row per Games with an image. Names are filled ONLY where the Games' Wikipedia "Mascot" section (wikipedia_edition_sections,
# already in the warehouse) states them; otherwise the name is '(name not recorded)' (column is NOT NULL; nothing is guessed). The description is that section's text.
MASCOT_NAMES = {
    "1976_summer": "Amik", "1976_winter": "Schneemann", "1980_winter": "Roni", "1984_summer": "Sam the Olympic Eagle", "1984_winter": "Vucko",
    "1988_summer": "Hodori", "1992_summer": "Cobi", "1992_winter": "Magique", "1996_summer": "Izzy", "1998_winter": "Sukki, Nokki, Lekki and Tsukki (the Snowlets)",
    "2000_summer": "Syd, Millie and Olly", "2002_winter": "Powder, Copper and Coal", "2004_summer": "Athena and Phevos", "2006_winter": "Neve and Gliz",
    "2008_summer": "Fuwa", "2010_winter": "Quatchi, Miga, Sumi and Mukmuk", "2012_summer": "Wenlock and Mandeville", "2016_summer": "Vinicius",
    "2022_winter": "Bing Dwen Dwen", "2024_summer": "Phryges", "2026_winter": "Tina and Milo",
}
con.execute("DELETE FROM mascots WHERE verification_status LIKE 'user-supplied%'")
n_m = 0
for gid, url in sorted(manifest["mascots"].items()):
    sec = con.execute("SELECT text FROM wikipedia_edition_sections WHERE games_id=? AND lower(heading) LIKE '%mascot%' AND text IS NOT NULL AND text!='' ORDER BY ordinal LIMIT 1", (gid,)).fetchone()
    wp = con.execute("SELECT url FROM wikipedia_edition_pages WHERE games_id=?", (gid,)).fetchone()
    con.execute("INSERT INTO mascots(games_id,name,description,image_url,source_url,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (gid, MASCOT_NAMES.get(gid) or "(name not recorded)", sec[0] if sec else None, url, wp[0] if (sec and wp) else None, "user-supplied image (licence not verified)"))
    n_m += 1
con.commit()
print(f"mascots {n_m} ({sum(1 for g in manifest['mascots'] if g in MASCOT_NAMES)} named from Wikipedia sections); Games without a mascot image:",
      sorted(g for g in games if re.match(r"(19[6-9]\d|20[0-2]\d)", g) and g not in manifest["mascots"]))
