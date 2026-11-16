#!/usr/bin/env python3
"""Local flag collection for every NOC in the warehouse (restartable; existing valid files are kept).

NOC code -> ISO alpha-3 (historical_nocs.iso_alpha3) -> ISO alpha-2 -> flag-icons SVG (MIT licence, flag designs are public domain), fetched from jsDelivr.
Historical / special codes with no ISO country (USSR, East / West Germany, Czechoslovakia, Yugoslavia, Unified Team, Olympic Athletes from Russia, Refugee team ...) use a named
Wikimedia Commons file; codes that represent a mixed or neutral delegation use the Olympic flag and are marked as such.  Output: frontend/public/assets/flags/<NOC>.svg
and flags.json (source, licence, kind per code) + reports/assets/flag_inventory.csv.   Usage: python scripts/download_flags.py"""
import csv
import json
import sqlite3
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/assets/flags"
H = {"User-Agent": "OlympicsHistoryProject/1.0 (offline research dataset; polite, cached, low volume)"}
FLAG_ICONS = "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/{}.svg"
WIKI_API = "https://en.wikipedia.org/w/api.php"   # also resolves Wikimedia Commons files (shared repository); commons.wikimedia.org itself is not always reachable
ISO_OVERRIDE = {"POR": "pt"}


def commons_url(title):
    """direct upload.wikimedia.org URL of a Commons file, or None when no such file exists (retries politely on HTTP 429)"""
    for attempt in range(6):
        time.sleep(1.2)
        try:
            r = requests.get(WIKI_API, params={"action": "query", "titles": "File:" + title, "prop": "imageinfo", "iiprop": "url", "format": "json"}, headers=H, timeout=30)
            if r.status_code == 429:
                time.sleep(8 * (attempt + 1))
                continue
            for page in r.json()["query"]["pages"].values():
                if "imageinfo" in page:
                    return page["imageinfo"][0]["url"].split("?")[0]
            return None
        except Exception:
            time.sleep(3)
    return None


# NOC codes that are not (or no longer) a country with an ISO code
COMMONS_FILE = {   # first title that exists wins
    "URS": ["Flag of the Soviet Union.svg"], "GDR": ["Flag of East Germany.svg"], "FRG": ["Flag of Germany.svg"], "EUA": ["Flag of Germany.svg"], "TCH": ["Flag of Czechoslovakia.svg"],
    "YUG": ["Flag of SFR Yugoslavia.svg", "Flag of Yugoslavia (1946-1992).svg"], "SCG": ["Flag of Serbia and Montenegro (1992-2006).svg", "Flag of Serbia and Montenegro.svg"],
    "AHO": ["Flag of the Netherlands Antilles (1986-2010).svg", "Flag of the Netherlands Antilles.svg"], "MAL": ["Flag of Malaya.svg", "Flag of Malaysia.svg"],
    "RHO": ["Flag of Rhodesia (1968-1979).svg", "Flag of Rhodesia.svg"], "UAR": ["Flag of Egypt (1958-1971).svg", "Flag of the United Arab Republic.svg"],
    "VNM": ["Flag of South Vietnam.svg"], "WIF": ["Flag of the West Indies Federation.svg", "Flag of West Indies Federation.svg"], "YAR": ["Flag of the Yemen Arab Republic.svg", "Flag of North Yemen.svg"],
    "YMD": ["Flag of South Yemen.svg"], 
}
OLYMPIC = "Olympic flag.svg"
OLYMPIC_CODES = {"ROC", "EUN", "OAR", "AIN", "IOA", "IOP", "EOR", "ROT", "COR", "ZZX", "UNK", "MIX", "ANZ", "BOH", "SAA"}   # mixed / neutral / unified teams: no national flag exists


def fetch(url, retries=4):
    for i in range(retries):
        try:
            r = requests.get(url, headers=H, timeout=40, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 120 and (b"<svg" in r.content[:400] or b"<?xml" in r.content[:100]):
                return r.content
            if r.status_code in (404, 400):
                return None
            if r.status_code == 429:
                time.sleep(25 * (i + 1))
                continue
        except requests.RequestException:
            pass
        time.sleep(2 * (i + 1))
    return None


def main():
    con = sqlite3.connect(f"file:{ROOT / 'data/olympics_warehouse.db'}?mode=ro", uri=True)
    iso3 = json.loads((ROOT / "data/iso3_to_iso2.json").read_text())
    names = {r[0]: (r[1], r[2]) for r in con.execute("SELECT noc_code, historical_name, iso_alpha3 FROM historical_nocs")}
    codes = sorted(set(names) | {r[0] for r in con.execute("SELECT DISTINCT noc_code FROM silver_participations WHERE noc_code IS NOT NULL")} | {r[0] for r in con.execute("SELECT host_noc FROM ref_host_noc WHERE host_noc IS NOT NULL")})
    OUT.mkdir(parents=True, exist_ok=True)
    old = json.loads((OUT / "flags.json").read_text(encoding="utf-8")) if (OUT / "flags.json").exists() else {}
    reg, missing = {}, []
    for noc in codes:
        dest = OUT / f"{noc}.svg"
        name, a3 = names.get(noc, (noc, None))
        a2 = ISO_OVERRIDE.get(noc) or iso3.get(a3 or "") or iso3.get(noc)
        if noc in OLYMPIC_CODES:
            url, kind, lic = commons_url(OLYMPIC) if not (dest.exists() and dest.stat().st_size > 120) else "(cached)", "olympic flag (no national flag)", "Olympic flag - Wikimedia Commons"
        elif noc in COMMONS_FILE:
            url = next((u for u in (commons_url(t) for t in COMMONS_FILE[noc]) if u), None) if not (dest.exists() and dest.stat().st_size > 120) else "(cached)"
            kind, lic = "historical flag", "Wikimedia Commons - see the file page of " + COMMONS_FILE[noc][0]
        elif a2:
            url, kind, lic = FLAG_ICONS.format(a2), "national flag", "flag-icons (MIT); flag design in the public domain"
        else:
            url, kind, lic = None, "unmapped", ""
        if dest.exists() and dest.stat().st_size > 120:
            ok = True
        elif url:
            data = fetch(url)
            ok = bool(data)
            if ok:
                dest.write_bytes(data)
        else:
            ok = False
        if ok:
            if url == "(cached)":
                url = old.get(noc, {}).get("source") or url
            reg[noc] = {"src": f"/assets/flags/{noc}.svg", "name": name, "kind": kind, "source": url, "license": lic}
        else:
            missing.append((noc, name, url))
    (OUT / "flags.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    (ROOT / "reports/assets").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "reports/assets/flag_inventory.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["noc", "name", "kind", "source_url", "license", "file"])
        for k, v in reg.items():
            w.writerow([k, v["name"], v["kind"], v["source"], v["license"], v["src"]])
        for noc, name, url in missing:
            w.writerow([noc, name, "MISSING", url or "", "", ""])
    kinds = {}
    for v in reg.values():
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    print(f"{len(codes)} NOC codes | flags saved {len(reg)} {kinds} | missing {len(missing)}: {[m[0] for m in missing]}")


if __name__ == "__main__":
    main()
