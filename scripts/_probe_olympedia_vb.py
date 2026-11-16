import requests
from bs4 import BeautifulSoup

ua = {"User-Agent": "OlympicsHistoricalCollector/1.0 (research; local-dev)"}
# event page for 1980 volleyball men
for url in [
    "https://www.olympedia.org/results/37280",
    "https://www.olympedia.org/results/37246",
]:
    r = requests.get(url, headers=ua, timeout=60)
    print("====", url, r.status_code)
    if r.status_code != 200:
        continue
    s = BeautifulSoup(r.text, "lxml")
    print("title", s.select_one("h1").get_text(" ", strip=True) if s.select_one("h1") else None)
    for i, t in enumerate(s.select("table")[:5]):
        headers = [th.get_text(" ", strip=True) for th in t.select("tr th")][:12]
        print("T", i, headers, "rows", len(t.select("tr")))
        for tr in t.select("tr")[1:4]:
            print(" ", [td.get_text(" ", strip=True) for td in tr.select("td")][:10])
