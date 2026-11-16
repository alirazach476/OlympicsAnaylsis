"""Probe Olympedia football event structure for fixtures/matches."""
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup

ua = {"User-Agent": "OlympicsHistoricalCollector/1.0 (research; local-dev)"}
# Paris 2024 edition 63 — football should have many match pages
index = requests.get("https://www.olympedia.org/editions/63/result", headers=ua, timeout=60)
soup = BeautifulSoup(index.text, "lxml")
fb = []
current_sport = None
for tr in soup.select("table tr"):
    cells = tr.select("td,th")
    if not cells:
        continue
    text = cells[0].get_text(" ", strip=True)
    links = [(a.get_text(" ", strip=True), a.get("href")) for a in tr.select("a")]
    if links and links[0][1] and "/sports/" in (links[0][1] or ""):
        current_sport = text
        continue
    if current_sport and "Football" in current_sport:
        fb.append((text, links, current_sport))

print("football events", len(fb))
for row in fb[:15]:
    print(row)

# fetch first football result
if fb:
    href = fb[0][1][0][1]
    if href.startswith("/"):
        href = "https://www.olympedia.org" + href
    r = requests.get(href, headers=ua, timeout=60)
    Path("data/raw/olympedia/sample_football_result.html").write_text(r.text, encoding="utf-8")
    s = BeautifulSoup(r.text, "lxml")
    print("title", s.select_one("h1").get_text(" ", strip=True) if s.select_one("h1") else None)
    # look for match / phase links
    match_links = []
    for a in s.select("a[href]"):
        h = a.get("href") or ""
        if "/results/" in h:
            match_links.append((a.get_text(" ", strip=True), h))
    print("nested result links", len(match_links))
    for m in match_links[:20]:
        print(" ", m)
    for i, t in enumerate(s.select("table")[:4]):
        headers = [th.get_text(" ", strip=True) for th in t.select("tr th")][:12]
        print("T", i, headers, "rows", len(t.select("tr")))
        for tr in t.select("tr")[1:5]:
            print(" ", [td.get_text(" ", strip=True) for td in tr.select("td")][:10])
