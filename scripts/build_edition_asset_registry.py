#!/usr/bin/env python3
"""Edition asset registry + per-edition colour themes for the frontend (offline, restartable, nothing downloaded).

Reads the editions from the warehouse (games), the asset files that are really on disk (frontend/public/assets: logos, backgrounds, mascots, pictograms) and the sport-labelled
pictograms collected from Wikipedia (sport_pictograms).  For every edition it
  * checks which assets exist and are readable (dimensions, format, size, duplicate detection by hash),
  * extracts a colour palette FROM THE EDITION'S OWN LOGO (falling back to its background image) - nothing is invented; with no readable image the edition gets the neutral historical theme,
  * writes frontend/public/assets/editions.json (the registry the theme engine and the pages use) and reports/assets/{asset_completeness.md,asset_inventory.csv}.
Licence / source are copied from the assets table: user-supplied images stay 'unverified' until a licence is confirmed - they are never presented as verified official artwork.
Usage: python scripts/build_edition_asset_registry.py"""
import colorsys
import csv
import hashlib
import json
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "frontend/public/assets"
OUT = ROOT / "reports/assets"
NEUTRAL = {"primary": "#8a7a52", "secondary": "#3f4a5c", "accent": "#c9a227", "source": "neutral historical theme (no readable edition artwork)"}
SPORT_SLUG = re.compile(r"[^a-z0-9]+")


def hex_of(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def usable(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return s >= 0.28 and 0.18 <= v <= 0.98      # skip white, black and grey


def palette_from_image(path: Path):
    try:
        im = Image.open(path)
        im.load()
    except Exception:
        return None
    im = im.convert("RGBA")
    im.thumbnail((140, 140))
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(bg, im).convert("RGB")
    alpha = im.getchannel("A")
    px = [p for p, a in zip(flat.getdata(), alpha.getdata()) if a > 200]
    px = [p for p in px if usable(*p)]
    if len(px) < 20:
        return None
    # quantise to 24 bins per channel group and count, then merge near neighbours
    cnt = Counter((r // 24, g // 24, b // 24) for r, g, b in px)
    sums = {}
    for (r, g, b) in px:
        k = (r // 24, g // 24, b // 24)
        s = sums.setdefault(k, [0, 0, 0, 0]); s[0] += r; s[1] += g; s[2] += b; s[3] += 1
    cols = sorted(((cnt[k], (v[0] / v[3], v[1] / v[3], v[2] / v[3])) for k, v in sums.items()), reverse=True)
    picked = []
    for n, rgb in cols:
        if all(sum(abs(a - b) for a, b in zip(rgb, o)) > 90 for o in picked):
            picked.append(rgb)
        if len(picked) == 4:
            break
    return [hex_of(c) for c in picked] if picked else None


def palette_from_svg(path: Path):
    txt = path.read_text(encoding="utf-8", errors="replace")
    cols = Counter(m.lower() for m in re.findall(r"#([0-9a-fA-F]{6})\b", txt))
    out = []
    for h, _ in cols.most_common(40):
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if usable(r, g, b) and all(sum(abs(a - b2) for a, b2 in zip((r, g, b), o)) > 90 for o in [tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in out]):
            out.append("#" + h)
        if len(out) == 4:
            break
    return out or None


def palette_for(path: Path):
    return palette_from_svg(path) if path.suffix.lower() == ".svg" else palette_from_image(path)


def luminance(hexv):
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def theme_from(palette, source):
    if not palette:
        return dict(NEUTRAL)
    # primary = most frequent saturated colour, secondary = next, accent = most vivid of the rest
    def vivid(c):
        h, s, v = colorsys.rgb_to_hsv(*(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))
        return s * v
    primary = palette[0]
    rest = palette[1:] or [palette[0]]
    secondary = rest[0]
    accent = max(palette, key=vivid)
    return {"primary": primary, "secondary": secondary, "accent": accent, "palette": palette, "on_primary": "#0b0f17" if luminance(primary) > 0.55 else "#ffffff", "source": source}


MAGIC = [(bytes([0x89, 0x50, 0x4E, 0x47]), ".png"), (bytes([0xFF, 0xD8, 0xFF]), ".jpg"), (b"GIF8", ".gif"), (b"<svg", ".svg"), (b"<?xml", ".svg")]


def sniff(path: Path):
    """real format from the first bytes (a webp saved as .svg does not display in a browser)"""
    head = path.read_bytes()[:16]
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif"
    for sig, ext in MAGIC:
        if head.startswith(sig):
            return ext
    return None


def fix_extension(path: Path, fixed: list):
    real = sniff(path)
    cur = ".jpg" if path.suffix.lower() == ".jpeg" else path.suffix.lower()
    if real and real != cur and not (real == ".svg" and cur == ".svg"):
        new = path.with_name(re.sub(r"\.(svg|png|jpe?g|webp|avif|gif)(\.(svg|png|jpe?g|webp|avif|gif))*$", "", path.name, flags=re.I) + real)
        if not new.exists():
            path.rename(new)
            fixed.append(f"{path.name} -> {new.name}")
            return new
        # a correctly named copy already exists (and is listed on its own): skip the mislabelled file instead of publishing a path the browser cannot display
        fixed.append(f"{path.name} skipped (wrong extension; {new.name} is used)")
        return None
    return path


def info(path: Path):
    d = {"file_format": path.suffix.lstrip(".").lower(), "bytes": path.stat().st_size}
    if path.suffix.lower() != ".svg":
        try:
            with Image.open(path) as im:
                d["image_width"], d["image_height"] = im.size
        except Exception:
            d["unreadable"] = True
    return d


import difflib
from urllib.parse import quote
import unicodedata

CITY_WORDS = {"rome", "tokyo", "mexico", "munich", "montreal", "moscow", "los", "angeles", "seoul", "barcelona", "atlanta", "sydney", "athens", "beijing", "london", "rio", "paris", "squaw", "valley", "innsbruck", "grenoble", "sapporo", "lake", "placid", "sarajevo", "calgary", "albertville", "lillehammer", "nagano", "salt", "torino", "vancouver", "sochi", "pyeongchang", "milano", "cortina"}
FIXED: list = []   # files whose extension did not match their real format
GENERIC_NAME = re.compile(r"^(image|screenshot|download|untitled)", re.I)


def clean_label(fname: str, year: int, city: str) -> str:
    """'Archery,_Athens_2004.png' / 'Archery_-_Paris_2024.svg.webp' / 'ALPINE SKIING 1.png' -> 'archery' / 'alpine skiing'"""
    stem = fname
    while Path(stem).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".avif", ".gif"):
        stem = Path(stem).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode().lower().replace("_", " ").replace("-", " ")
    stem = re.sub(rf"\b{year}\b|\b{re.escape(city.lower())}\b", " ", stem)
    stem = re.sub(r"[,.()]+", " ", stem)
    stem = re.sub(r"\b(" + "|".join(sorted(CITY_WORDS | set(city.lower().split()))) + r")\b", " ", stem)
    stem = re.sub(r"\s+\d+$", "", stem.strip())
    return re.sub(r"\s+", " ", stem).strip()


# file-name label (start of text) -> (canonical sport, discipline).  Order matters: first match wins.
CANON = [
    (r"alpine skiing", "Alpine Skiing"), (r"cross country", "Cross Country Skiing"), (r"nordic combined", "Nordic Combined"), (r"ski jumping", "Ski Jumping"),
    (r"(freestyle|freeski|aerials|moguls|ballet|ski cross)", "Freestyle Skiing"), (r"snowboard", "Snowboarding"), (r"short track", "Short Track Speed Skating"), (r"speed skating", "Speed Skating"),
    (r"figure skating", "Figure Skating"), (r"ice hockey", "Ice Hockey"), (r"(bobsleigh|bobsled)", "Bobsleigh"), (r"luge", "Luge"), (r"skeleton", "Skeleton"), (r"biathlon", "Biathlon"), (r"curling", "Curling"),
    (r"ski mountaineering", "Ski Mountaineering"), (r"archery", "Archery"), (r"(athletics|atheletes|marathon|track and field)", "Athletics"), (r"badminton", "Badminton"), (r"baseball", "Baseball"),
    (r"3x3", "3x3 Basketball"), (r"basketball", "Basketball"), (r"beach volleyball", "Beach Volleyball"), (r"volleyball", "Volleyball"), (r"boxing", "Boxing"), (r"canoe\w*", "Canoeing"),
    (r"cycling", "Cycling"), (r"diving", "Diving"), (r"equestrian", "Equestrian"), (r"fencing", "Fencing"), (r"football", "Football"), (r"golf", "Golf"),
    (r"rhythmic", "Rhythmic Gymnastics"), (r"(artistic gymnastics|gymnastics|trampolin)", "Gymnastics"), (r"handball", "Handball"), (r"(field hockey|hockey)", "Hockey"), (r"judo", "Judo"), (r"karate", "Karate"),
    (r"modern pentathlon", "Modern Pentathlon"), (r"rowing", "Rowing"), (r"rugby", "Rugby Sevens"), (r"(sailing|yachting)", "Sailing"), (r"shooting", "Shooting"), (r"skateboard", "Skateboarding"),
    (r"sport climbing", "Sport Climbing"), (r"surfing", "Surfing"), (r"(synch\w*|artistic swimming)", "Artistic Swimming"), (r"swimming", "Swimming"), (r"table tennis", "Table Tennis"), (r"taekwondo", "Taekwondo"),
    (r"tennis", "Tennis"), (r"triathlon", "Triathlon"), (r"water polo", "Water Polo"), (r"weightlifting", "Weightlifting"), (r"wrestling", "Wrestling"), (r"breaking", "Breaking"), (r"softball", "Softball"),
    (r"bowling", "Bowling"), (r"(pelota|basque)", "Basque Pelota"), (r"roller hockey", "Roller Hockey"), (r"wushu", "Wushu"), (r"aquatics", "Aquatics"),
]
NON_SPORT = re.compile(r"olympic village|ceremon|mascot|torch|emblem")


def link_sport(label, sports):
    """canonical sport from the file-name label (alias table above) + the remaining words as the discipline; sport_id only when the warehouse has that sport"""
    if NON_SPORT.search(label):
        return None, None
    for rx, canon in CANON:
        m = re.match(rf"^{rx}\b", label) or (re.search(rf"\b{rx}\b", label) if rx in (r"3x3",) else None)
        if m:
            rest = re.sub(r"^\s*", "", label[m.end():]).strip() or None
            return canon, rest
    m = difflib.get_close_matches(label, [r[1].lower() for r in CANON_NAMES], n=1, cutoff=0.82)
    return (next(r[1] for r in CANON_NAMES if r[1].lower() == m[0]), None) if m else (None, None)


CANON_NAMES = [(None, c) for _, c in CANON]


def main():
    con = sqlite3.connect(f"file:{ROOT / 'data/olympics_warehouse.db'}?mode=ro", uri=True)
    games = con.execute("SELECT games_id, year, season, host_city, host_country, official_edition_name FROM games ORDER BY year, season").fetchall()
    assets_rows = {(r[0], r[1]): r[2:] for r in con.execute("SELECT games_id, asset_type, license, verification_status, source_page, attribution FROM assets WHERE asset_type!='sport_pictogram'")}
    sports = {}
    for sid, nm, n in con.execute("SELECT s.sport_id, s.sport_name, (SELECT COUNT(*) FROM athlete_participations p WHERE p.sport_id=s.sport_id) FROM sports s"):
        k = nm.lower()
        if k not in sports or n > sports[k][1]:
            sports[k] = (sid, n)
    sports = {k: v[0] for k, v in sports.items()}
    labelled = {}
    hashes, inventory, registry = {}, [], {}
    for gid, year, season, city, country, name in games:
        folder = PUB / "labelled_pictograms" / gid
        e = {"editionId": gid, "name": f"{city} {year}", "officialName": name, "season": season, "year": year, "hostCity": city, "hostCountry": country, "assets": {"logo": None, "background": None, "mascots": [], "pictograms": [], "posters": [], "venues": []}}
        for kind, folder_name, key in (("logo", "logos", "logo"), ("background", "backgrounds", "background")):
            f = next(iter(sorted((PUB / folder_name).glob(f"{gid}.*"))), None)
            if f:
                e["assets"][key] = f"/assets/{folder_name}/{f.name}"
                meta = info(f)
                row = assets_rows.get((gid, "edition_logo" if kind == "logo" else "edition_background"))
                e["assets"][key + "Meta"] = {**meta, "license": row[0] if row else "unknown", "verification": row[1] if row else "unverified"}
        for f in sorted((PUB / "mascots").glob(f"{gid}.*")):
            row = assets_rows.get((gid, "mascot"))
            e["assets"]["mascots"].append({"src": f"/assets/mascots/{f.name}", "name": None, "nameRecorded": False, **info(f), "license": row[0] if row else "unknown", "verification": row[1] if row else "unverified"})
        pd = PUB / "pictograms" / gid
        if pd.exists():
            for f in sorted(pd.iterdir(), key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)]):
                if f.is_file():
                    f = fix_extension(f, FIXED)
                    if f is None:
                        continue
                    h = hashlib.md5(f.read_bytes()).hexdigest()
                    dup = hashes.setdefault(h, f"{gid}/{f.name}")
                    label = None if GENERIC_NAME.match(f.name) else clean_label(f.name, year, city)
                    sp, disc = link_sport(label, sports) if label else (None, None)
                    e["assets"]["pictograms"].append({"src": f"/assets/pictograms/{gid}/{quote(f.name, safe="/,()'!~*-._")}", "label": label, "sport": sp, "sportId": sports.get(sp.lower()) if sp else None, "discipline": disc, "sportLinked": bool(sp), "linkedBy": "file name" if sp else None, "duplicateOf": None if dup == f"{gid}/{f.name}" else dup, **info(f)})
        pal = None
        src_used = None
        for key in ("logo", "background"):
            if e["assets"][key]:
                pal = palette_for(PUB / e["assets"][key].replace("/assets/", "", 1))
                if pal:
                    src_used = f"extracted from the edition {key}"
                    break
        e["theme"] = theme_from(pal, src_used)
        a = e["assets"]
        flags = {"logo": bool(a["logo"]), "background": bool(a["background"]), "mascot": bool(a["mascots"]), "pictograms": bool(a["pictograms"]), "sportLinkedPictograms": any(p["sportLinked"] for p in a["pictograms"]), "theme": bool(pal)}
        e["completeness"] = {**flags, "level": "complete" if all(flags[k] for k in ("logo", "background", "mascot", "pictograms")) else "partial" if flags["logo"] else "neutral"}
        registry[gid] = e
        for k in ("logo", "background"):
            if a[k]:
                inventory.append([gid, k, a[k], a[k + "Meta"].get("file_format"), a[k + "Meta"].get("image_width"), a[k + "Meta"].get("image_height"), a[k + "Meta"]["verification"]])
        for m in a["mascots"]:
            inventory.append([gid, "mascot", m["src"], m["file_format"], m.get("image_width"), m.get("image_height"), m["verification"]])
        for p in a["pictograms"]:
            inventory.append([gid, "pictogram" + (f": {p['sport']}" if p["sportLinked"] else " (sport not recorded)"), p["src"], p["file_format"], p.get("image_width"), p.get("image_height"), "user-supplied; sport linked by file name" if p["sportLinked"] else "user-supplied; sport not recorded"])
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "editions.json").write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(), "neutralTheme": NEUTRAL, "editions": registry}, ensure_ascii=False), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "asset_inventory.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["edition", "asset_type", "path", "format", "width", "height", "verification"])
        w.writerows(inventory)
    md = ["# Edition asset completeness\n", f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}.  Assets are the files really present in `frontend/public/assets`; nothing here was downloaded or invented.\n",
          "| Edition | Logo | Background | Mascot | Pictograms | Sport-linked pictograms | Theme source | Level |\n|---|---|---|---|---|---|---|---|"]
    for gid, e in registry.items():
        a, c = e["assets"], e["completeness"]
        md.append(f"| {e['name']} ({e['season']}) | {'yes' if c['logo'] else 'MISSING'} | {'yes' if c['background'] else 'MISSING'} | {len(a['mascots']) or 'MISSING'} | {len(a['pictograms'])} | {sum(1 for p in a['pictograms'] if p['sportLinked'])} | {e['theme']['source']} | {c['level']} |")
    n = len(registry)
    md.append(f"\n**{n} editions.** logos {sum(1 for e in registry.values() if e['assets']['logo'])}, backgrounds {sum(1 for e in registry.values() if e['assets']['background'])}, mascot images {sum(1 for e in registry.values() if e['assets']['mascots'])}, "
              f"editions with pictogram images {sum(1 for e in registry.values() if e['completeness']['pictograms'])}, with sport-linked pictograms {sum(1 for e in registry.values() if e['completeness']['sportLinkedPictograms'])}.")
    md.append("\nLicences: logos, backgrounds, mascots and the unlabelled pictograms were supplied by the project owner and are marked *unverified* (no licence recorded). Mascot names are not recorded for any edition. "
              "Unlabelled pictogram images have no recorded sport, so they are shown as an edition gallery and are NOT linked to a sport.\n")
    (OUT / "asset_completeness.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    dups = sum(1 for e in registry.values() for p in e["assets"]["pictograms"] if p["duplicateOf"])
    if FIXED:
        print("renamed (extension did not match the real format):", FIXED)
    print(f"{n} editions | complete {sum(1 for e in registry.values() if e['completeness']['level'] == 'complete')} | partial {sum(1 for e in registry.values() if e['completeness']['level'] == 'partial')} | neutral {sum(1 for e in registry.values() if e['completeness']['level'] == 'neutral')} | themes extracted {sum(1 for e in registry.values() if e['completeness']['theme'])} | duplicate pictograms {dups}")


if __name__ == "__main__":
    main()
