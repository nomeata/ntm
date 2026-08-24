"""Schlagworte: Normalisierung, Hierarchie, Typeahead."""

import pytest

from ntm import tags


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Sprache/Grammatik/Kasus", "Sprache/Grammatik/Kasus"),
        ("  Sprache / Grammatik ", "Sprache/Grammatik"),
        ("/Sprache//Grammatik/", "Sprache/Grammatik"),
        ("Sprache/   /Grammatik", "Sprache/Grammatik"),
        ("Mit   Eltern", "Mit Eltern"),
        ("   ", ""),
    ],
)
def test_normalize_tag(raw, expected):
    assert tags.normalize_tag(raw) == expected


def test_normalize_tags_dedupes_case_insensitively():
    assert tags.normalize_tags(
        ["Sprache/Grammatik", "sprache/grammatik", "", "Motorik"]
    ) == ["Sprache/Grammatik", "Motorik"]


def test_ancestors():
    assert tags.ancestors("Sprache/Grammatik/Kasus") == [
        "Sprache",
        "Sprache/Grammatik",
        "Sprache/Grammatik/Kasus",
    ]
    assert tags.ancestors("Sprache/Grammatik", include_self=False) == ["Sprache"]


def test_ober_tag_schliesst_unter_tags_ein():
    entry_tags = ["Sprache/Grammatik/Kasus"]
    assert tags.matches_filter(entry_tags, "Sprache")
    assert tags.matches_filter(entry_tags, "Sprache/Grammatik")
    assert tags.matches_filter(entry_tags, "Sprache/Grammatik/Kasus")
    assert tags.matches_filter(entry_tags, "sprache/grammatik")  # Schreibweise egal


def test_unter_tag_schliesst_ober_tag_nicht_ein():
    assert not tags.matches_filter(["Sprache"], "Sprache/Grammatik")


def test_kein_praefix_treffer_mitten_im_segment():
    # "Sprach" ist kein Oberbegriff von "Sprache" – die Grenze ist der Slash.
    assert not tags.matches_filter(["Sprache/Grammatik"], "Sprach")


def test_geschwister_treffen_sich_nicht():
    assert not tags.matches_filter(["Sprache/Wortschatz"], "Sprache/Grammatik")


def test_mehrere_filter_sind_und_verknuepft():
    entry_tags = ["Sprache/Grammatik/Kasus", "Format/Spiel"]
    assert tags.matches_all_filters(entry_tags, ["Sprache", "Format/Spiel"])
    assert not tags.matches_all_filters(entry_tags, ["Sprache", "Motorik"])


def test_universe_zaehlt_oberbegriffe_mit():
    universe = tags.build_universe(
        [
            ["Sprache/Grammatik/Kasus"],
            ["Sprache/Wortschatz"],
            ["Motorik"],
        ]
    )
    assert universe["Sprache"] == 2
    assert universe["Sprache/Grammatik"] == 1
    assert universe["Sprache/Grammatik/Kasus"] == 1
    assert universe["Motorik"] == 1


def test_universe_zaehlt_eintrag_pro_oberbegriff_nur_einmal():
    universe = tags.build_universe([["Sprache/Grammatik", "Sprache/Wortschatz"]])
    assert universe["Sprache"] == 1


def test_universe_behaelt_erste_schreibweise():
    universe = tags.build_universe([["Sprache/Grammatik"], ["sprache/grammatik"]])
    assert universe["Sprache/Grammatik"] == 2
    assert "sprache/grammatik" not in universe


def _suggested(universe, query):
    return [item.tag for item in tags.suggest(universe, query)]


def test_typeahead_trifft_teilsegmente():
    universe = tags.build_universe([["Sprache/Grammatik/Kasus"], ["Motorik/Grafomotorik"]])
    assert "Sprache/Grammatik/Kasus" in _suggested(universe, "kasus")
    assert "Sprache/Grammatik/Kasus" in _suggested(universe, "gramm")
    assert "Motorik/Grafomotorik" in _suggested(universe, "grafo")


def test_typeahead_mit_pfadanfrage():
    universe = tags.build_universe([["Sprache/Grammatik/Kasus"], ["Sprache/Wortschatz"]])
    found = _suggested(universe, "Sprache/Gram")
    assert "Sprache/Grammatik" in found
    assert "Sprache/Wortschatz" not in found


def test_typeahead_ignoriert_umlaut_schreibweise():
    universe = tags.build_universe([["Erzählen/Märchen"]])
    assert _suggested(universe, "marchen") == ["Erzählen/Märchen"]
    assert _suggested(universe, "maerchen") == ["Erzählen/Märchen"]


def test_typeahead_ordnet_exakte_treffer_nach_vorne():
    universe = tags.build_universe(
        [["Spiel"], ["Spiel"], ["Format/Spielesammlung"], ["Format/Spielesammlung"]]
    )
    assert _suggested(universe, "spiel")[0] == "Spiel"


def test_typeahead_ohne_anfrage_liefert_haeufigstes_zuerst():
    universe = tags.build_universe([["Sprache"], ["Sprache"], ["Motorik"]])
    assert _suggested(universe, "")[0] == "Sprache"
