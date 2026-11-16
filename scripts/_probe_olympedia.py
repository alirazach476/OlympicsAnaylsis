from pathlib import Path
import requests
from bs4 import BeautifulSoup

ua = {"User-Agent": "OlympicsHistoricalCollector/1.0 (research; local-dev)"}
url = "https://www.olympedia.org/editions/15/result"
r = requests.get(url, headers=ua, timeout=60)
soup = BeautifulSoup(r.text, "lxml")
table = soup.select_one("table")
print("rows", len(table.select("tr")) if table else 0)
for tr in (table.select("tr")[:25] if table else []):
    cells = [td.get_text(" ", strip=True) for td in tr.select("td,th")]
    links = [(a.get_text(" ", strip=True), a.get("href")) for a in tr.select("a")]
    print(cells[:6], links[:4])

# drill into one event result page
# find first /results/ link
href = None
for a in soup.select("a[href]"):
    h = a.get("href") or ""
    if "/results/" in h:
        href = h
        print("first result link", a.get_text(" ", strip=True), h)
        break
if href:
    if href.startswith("/"):
        href = "https://www.olympedia.org" + href
    r2 = requests.get(href, headers=ua, timeout=60)
    Path("data/raw/olympedia/sample_result.html").write_text(r2.text, encoding="utf-8")
    s2 = BeautifulSoup(r2.text, "lxml")
    print("result title", s2.select_one("h1").get_text(" ", strip=True) if s2.select_one("h1") else None)
    print("tables", len(s2.select("table")))
    for i, t in enumerate(s2.select("table")[:3]):
        headers = [th.get_text(" ", strip=True) for th in t.select("tr th")][:10]
        print("T", i, headers, "rows", len(t.select("tr")))
        for tr in t.select("tr")[1:4]:
            print(" ", [td.get_text(" ", strip=True) for td in tr.select("td")][:8])
