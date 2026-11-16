from backend.parsers.medal_tables import parse_medal_table


def test_parse_simple_medal_table():
    table = {
        "headers": ["Rank", "NOC", "Gold", "Silver", "Bronze", "Total"],
        "rows": [
            ["1", "Soviet Union (URS)", "43", "29", "31", "103"],
            ["2", "United States (USA)", "34", "21", "16", "71"],
        ],
    }
    rows = parse_medal_table(table)
    assert len(rows) == 2
    assert rows[0]["gold"] == 43
    assert rows[0]["country_name"].startswith("Soviet Union")
    assert rows[1]["total"] == 71
