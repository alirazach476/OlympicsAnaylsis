from backend.scrapers.olympedia.results import HISTORICAL_LABEL_RE, MATCH_LABEL_RE


def test_match_like_labels_are_followed():
    for label in ["Match #4", "Bout 1/2", "Bout 3/4", "Play-Off", "Barrage", "Tie-Break", "Replay", "Final"]:
        assert MATCH_LABEL_RE.search(label), label


def test_other_labels_not_matches():
    for label in ["Heat 2", "Lift #3", "Semifinals"]:
        assert not MATCH_LABEL_RE.search(label) or label == "Semifinals" and False


def test_historical_references_skipped():
    assert HISTORICAL_LABEL_RE.search("Helsinki 1952 Olympics")
    assert not HISTORICAL_LABEL_RE.search("Bout 1/2")
