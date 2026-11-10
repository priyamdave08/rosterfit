import pandas as pd

from rosterfit.engine.context import rank_search

NAMES = pd.Series({"nembhan01": "Andrew Nembhard", "wembavi01": "Victor Wembanyama", "doncilu01": "Luka Dončić",
                   "castlco01": "Colin Castleton", "castlst01": "Stephon Castle", "foxde01": "De'Aaron Fox"})


def test_prefix_of_any_name_part_beats_fuzzy():
    assert rank_search(NAMES, "wemb")[0] == "wembavi01"


def test_accents_and_punctuation_ignored():
    assert rank_search(NAMES, "doncic")[0] == "doncilu01"
    assert rank_search(NAMES, "deaaron")[0] == "foxde01"
    assert rank_search(NAMES, "De'Aaron")[0] == "foxde01"


def test_exact_word_beats_longer_word():
    assert rank_search(NAMES, "castle")[:2] == ["castlst01", "castlco01"]


def test_typos_still_match():
    assert rank_search(NAMES, "wembanyam")[0] == "wembavi01"
    assert rank_search(NAMES, "wembenyama")[0] == "wembavi01"


def test_empty_query_keeps_input_order_and_garbage_returns_nothing():
    assert rank_search(NAMES, "", limit=None) == list(NAMES.index)
    assert rank_search(NAMES, "zzzzqqq") == []
