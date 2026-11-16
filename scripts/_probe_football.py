from backend.scrapers.wikipedia.mediawiki import MediaWikiClient
from backend.scrapers.wikipedia.extractors import parse_html_bundle
from bs4 import BeautifulSoup

c = MediaWikiClient()
titles = [
    "Football at the 1960 Summer Olympics",
    "Football at the 2024 Summer Olympics",
    "Football at the 2024 Summer Olympics – Men's tournament",
]
for title in titles:
    print("====", title)
    try:
        html = c.get_html(title)
    except Exception as e:
        print("ERR", e)
        continue
    p = parse_html_bundle(html)
    print("tables", len(p["tables"]))
    for t in p["tables"][:5]:
        print(" ", t.get("caption"), t.get("headers")[:8], "rows", t.get("row_count"))
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("div.mw-parser-output a[href]"):
        href = a.get("href") or ""
        text = a.get_text(" ", strip=True)
        low = href.lower()
        if "football_at_the_" in low and any(
            k in low for k in ("squad", "match", "tournament", "group", "final", "knockout")
        ):
            print(" link", text, href)
