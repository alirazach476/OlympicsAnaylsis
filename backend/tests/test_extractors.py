from backend.scrapers.wikipedia.extractors import parse_html_bundle

SAMPLE = """
<html><body><div class="mw-parser-output">
<table class="infobox">
  <tr><th>Host city</th><td>Rome</td></tr>
  <tr><th>Nations</th><td>83</td></tr>
</table>
<h2 id="Medal_table">Medal table</h2>
<table class="wikitable">
  <tr><th>NOC</th><th>Gold</th><th>Silver</th><th>Bronze</th></tr>
  <tr><td>URS</td><td>43</td><td>29</td><td>31</td></tr>
  <tr><td>USA</td><td>34</td><td>21</td><td>16</td></tr>
</table>
<a href="/wiki/Athletics_at_the_1960_Summer_Olympics">Athletics</a>
<a href="/wiki/File:Example.svg">file</a>
<ol class="references"><li id="cite_note-1">Official report <a href="https://example.com">link</a></li></ol>
</div></body></html>
"""


def test_parse_infobox_tables_links():
    data = parse_html_bundle(SAMPLE)
    assert data["infobox"]["Host city"] == "Rome"
    assert data["tables"][0]["headers"][:2] == ["NOC", "Gold"]
    assert data["tables"][0]["rows"][0][0] == "URS"
    titles = [l["title"] for l in data["html_links"]]
    assert "Athletics at the 1960 Summer Olympics" in titles
    assert not any(t.startswith("File:") for t in titles)
    assert data["references"]
