import requests
from bs4 import BeautifulSoup

ua = {"User-Agent": "OlympicsHistoricalCollector/1.0 (research; local-dev)"}
url = "https://www.olympedia.org/results/2002394"
r = requests.get(url, headers=ua, timeout=60)
s = BeautifulSoup(r.text, "lxml")
print("title", s.select_one("h1").get_text(" ", strip=True) if s.select_one("h1") else None)
for i, t in enumerate(s.select("table")[:6]):
    headers = [th.get_text(" ", strip=True) for th in t.select("tr th")][:15]
    print("T", i, headers, "rows", len(t.select("tr")))
    for tr in t.select("tr")[:8]:
        print(" ", [c.get_text(" ", strip=True) for c in tr.select("td,th")][:12])
# breadcrumbs / meta
for sel in [".breadcrumb", "ol.breadcrumb", "#content h1", "table.biodata"]:
    els = s.select(sel)
    print("sel", sel, len(els))
    for e in els[:2]:
        print(" ", e.get_text(" | ", strip=True)[:200])
