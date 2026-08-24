"""Suche und Filter."""

from conftest import indexed, make_entry

from ntm import ages
from ntm.query import SearchQuery, search
from ntm.text import tokenize


def titles(result):
    return [entry.title for entry in result]


def sample():
    return indexed(
        make_entry(
            "a",
            title="Kasus-Memory",
            description="Memory zu Dativ und Akkusativ",
            text="Die Karten werden gemischt.",
            tags=["Sprache/Grammatik/Kasus", "Format/Spiel"],
            age_from=7,
            age_to=12,
            book="Sprachförderung konkret",
        ),
        make_entry(
            "b",
            title="Wortschatzkiste",
            description="Bildkarten zum Wortfeld Küche",
            text="Sortieren nach Oberbegriffen, auch mit Eltern zu Hause.",
            tags=["Sprache/Wortschatz"],
            age_from=5,
            age_to=9,
            book="Sprachförderung konkret",
        ),
        make_entry(
            "c",
            title="Elternbrief Mundmotorik",
            description="Übungen für zu Hause",
            tags=["Motorik/Mundmotorik", "Mit Eltern"],
            age_from=ages.PARENTS,
            age_to=ages.PARENTS,
            book="digital",
        ),
    )


def test_ohne_filter_alles_alphabetisch():
    assert titles(search(sample(), SearchQuery())) == [
        "Elternbrief Mundmotorik",
        "Kasus-Memory",
        "Wortschatzkiste",
    ]


def test_volltext_ueber_titel_beschreibung_text():
    assert titles(search(sample(), SearchQuery(q="memory"))) == ["Kasus-Memory"]
    assert titles(search(sample(), SearchQuery(q="bildkarten"))) == ["Wortschatzkiste"]
    assert titles(search(sample(), SearchQuery(q="gemischt"))) == ["Kasus-Memory"]


def test_volltext_ignoriert_gross_klein_und_umlaute():
    assert titles(search(sample(), SearchQuery(q="KÜCHE"))) == ["Wortschatzkiste"]
    assert titles(search(sample(), SearchQuery(q="kuche"))) == ["Wortschatzkiste"]
    assert titles(search(sample(), SearchQuery(q="kueche"))) == ["Wortschatzkiste"]


def test_mehrere_tokens_sind_und_verknuepft():
    assert titles(search(sample(), SearchQuery(q="memory karten"))) == ["Kasus-Memory"]
    assert search(sample(), SearchQuery(q="memory bildkarten")) == []


def test_tokens_duerfen_in_verschiedenen_feldern_stehen():
    # "elternbrief" steht im Titel, "übungen" in der Beschreibung.
    assert titles(search(sample(), SearchQuery(q="elternbrief übungen"))) == [
        "Elternbrief Mundmotorik"
    ]


def test_anfuehrungszeichen_halten_woerter_zusammen():
    assert tokenize('"wortfeld küche" memory') == ["wortfeld küche", "memory"]
    assert titles(search(sample(), SearchQuery(q='"wortfeld küche"'))) == [
        "Wortschatzkiste"
    ]


def test_titeltreffer_stehen_vor_textreffern():
    entries = indexed(
        make_entry("a", title="Nebensache", text="Ausführlich über Memory"),
        make_entry("b", title="Memory für den Wortschatz"),
    )
    assert titles(search(entries, SearchQuery(q="memory"))) == [
        "Memory für den Wortschatz",
        "Nebensache",
    ]


def test_tagfilter_schliesst_untertags_ein():
    assert titles(search(sample(), SearchQuery(tags=["Sprache"]))) == [
        "Kasus-Memory",
        "Wortschatzkiste",
    ]
    assert titles(search(sample(), SearchQuery(tags=["Sprache/Grammatik"]))) == [
        "Kasus-Memory"
    ]


def test_mehrere_tagfilter_kombinieren_sich():
    assert titles(search(sample(), SearchQuery(tags=["Sprache", "Format/Spiel"]))) == [
        "Kasus-Memory"
    ]
    assert search(sample(), SearchQuery(tags=["Sprache", "Motorik"])) == []


def test_eltern_ist_ein_ganz_normales_tag():
    assert titles(search(sample(), SearchQuery(tags=["Mit Eltern"]))) == [
        "Elternbrief Mundmotorik"
    ]


def test_altersfilter_ist_ein_einzelner_wert():
    assert titles(search(sample(), SearchQuery(age=8))) == [
        "Kasus-Memory",
        "Wortschatzkiste",
    ]
    assert titles(search(sample(), SearchQuery(age=11))) == ["Kasus-Memory"]
    assert titles(search(sample(), SearchQuery(age=5))) == ["Wortschatzkiste"]


def test_altersfilter_eltern():
    assert titles(search(sample(), SearchQuery(age=ages.PARENTS))) == [
        "Elternbrief Mundmotorik"
    ]


def test_filter_und_volltext_zusammen():
    query = SearchQuery(q="sortieren", tags=["Sprache"], age=6)
    assert titles(search(sample(), query)) == ["Wortschatzkiste"]
    assert search(sample(), SearchQuery(q="sortieren", age=15)) == []
