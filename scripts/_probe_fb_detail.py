from urllib.parse import unquote
from bs4 import BeautifulSoup
from backend.scrapers.wikipedia.mediawiki import MediaWikiClient
from backend.scrapers.wikipedia.extractors import parse_html_bundle

c = MediaWikiClient()
titles = [
    "Football at the 1960 Summer Olympics – Group 1",
    "Football at the 1960 Summer Olympics – Men's team squads",
    "Football at the 1960 Summer Olympics – Knockout stage",
]
for title in titles:
    print("====", title)
    html = c.get_html(title)
    Path = __import__("pathlib").Path
    safe = title.replace(" ", "_").replace("–", "-")[:80]
    Path("data/raw/wikipedia/football_probe").mkdir(parents=True, exist_ok=True)
    Path(f"data/raw/wikipedia/football_probe/{safe}.html").write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    boxes = soup.select("div.footballbox, div.vevent, table.wikitable")
    print("footballboxes", len(soup.select("div.footballbox")))
    print("vevent", len(soup.select("div.vevent")))
    print("wikitables", len(soup.select("table.wikitable")))
    for box in soup.select("div.footballbox")[:2]:
        print("BOX", " ".join(box.stripped_strings)[:240])
    p = parse_html_bundle(html)
    for t in p["tables"][:3]:
        print("T", t.get("headers")[:6], t.get("rows")[:2])
    # squad headings
    for h in soup.select("h2, h3")[:12]:
        print("H", h.get_text(" ", strip=True)[:80])
