"""Die Altersachse: 5 … 21+ … Eltern."""

import pytest

from ntm import ages
from ntm.models import EntryInput


def test_parse_zahlen():
    assert ages.parse_age(5) == 5
    assert ages.parse_age("12") == 12
    assert ages.parse_age(" 8 ") == 8


def test_parse_21_plus():
    assert ages.parse_age("21+") == 21
    assert ages.parse_age(21) == 21


def test_parse_eltern():
    assert ages.parse_age("Eltern") == ages.PARENTS
    assert ages.parse_age("eltern") == ages.PARENTS
    assert ages.parse_age(ages.PARENTS) == ages.PARENTS


@pytest.mark.parametrize("value", [4, 23, "", "vier", None, True])
def test_parse_lehnt_unsinn_ab(value):
    with pytest.raises(ValueError):
        ages.parse_age(value)


def test_serialisierung_bleibt_lesbar():
    assert ages.serialize_age(7) == 7
    assert ages.serialize_age(21) == 21
    assert ages.serialize_age(ages.PARENTS) == "Eltern"


def test_beschriftung():
    assert ages.age_label(7) == "7"
    assert ages.age_label(21) == "21+"
    assert ages.age_label(ages.PARENTS) == "Eltern"
    assert ages.range_label(7, 12) == "7–12"
    assert ages.range_label(9, 9) == "9"
    assert ages.range_label(5, ages.PARENTS) == "5–Eltern"


def test_achse_endet_bei_eltern():
    axis = ages.axis()
    assert axis[0] == ages.AGE_MIN
    assert axis[-1] == ages.PARENTS
    assert len(axis) == 18  # 5..21 plus Eltern


def test_bereich_enthaelt_wert():
    assert ages.matches_age(7, 12, 7)
    assert ages.matches_age(7, 12, 12)
    assert not ages.matches_age(7, 12, 6)
    assert not ages.matches_age(7, 12, 13)


def test_eltern_liegt_oberhalb_von_21():
    # Ein Bereich, der bei 21+ endet, meint keine Eltern.
    assert not ages.matches_age(5, 21, ages.PARENTS)
    # Wer Eltern einschließen will, zieht den Bereich bis dorthin.
    assert ages.matches_age(5, ages.PARENTS, ages.PARENTS)
    assert ages.matches_age(5, ages.PARENTS, 21)
    # Reines Elternmaterial taucht bei keiner Altersstufe auf.
    assert ages.matches_age(ages.PARENTS, ages.PARENTS, ages.PARENTS)
    assert not ages.matches_age(ages.PARENTS, ages.PARENTS, 21)


def test_modell_nimmt_eltern_entgegen():
    entry = EntryInput(title="x", age_from=12, age_to="Eltern")
    assert entry.age_to == ages.PARENTS
    assert entry.model_dump(mode="json")["age_to"] == "Eltern"


def test_modell_dreht_verkehrte_bereiche():
    entry = EntryInput(title="x", age_from="Eltern", age_to=8)
    assert (entry.age_from, entry.age_to) == (8, ages.PARENTS)
