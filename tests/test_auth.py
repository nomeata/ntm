"""Magic-Link-Tokens und die Nutzerliste."""

import pytest

from ntm import auth
from ntm.config import parse_users

USERS = ["anna@example.org", "bea@example.org"]


# -- Schlüssel ---------------------------------------------------------


def test_secret_wird_angelegt_und_wiederverwendet(tmp_path):
    first = auth.load_secret(tmp_path)
    second = auth.load_secret(tmp_path)
    assert first == second
    path = tmp_path / auth.SECRET_FILE
    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600


def test_neues_secret_macht_alte_tokens_ungueltig(tmp_path):
    secret = auth.load_secret(tmp_path)
    token = auth.token_for(secret, USERS[0])
    (tmp_path / auth.SECRET_FILE).unlink()
    fresh = auth.load_secret(tmp_path)
    assert auth.token_user(fresh, token, USERS) is None


# -- Tokens ------------------------------------------------------------


def test_token_roundtrip():
    secret = b"testschluessel"
    token = auth.token_for(secret, " Anna@Example.org ")
    assert auth.token_user(secret, token, USERS) == "anna@example.org"


def test_token_traegt_die_adresse():
    secret = b"testschluessel"
    for user in USERS:
        token = auth.token_for(secret, user)
        assert auth.token_user(secret, token, USERS) == user


def test_kaputte_tokens():
    secret = b"testschluessel"
    good = auth.token_for(secret, USERS[0])
    encoded, _, mac = good.partition(".")
    assert auth.token_user(secret, "", USERS) is None
    assert auth.token_user(secret, "kein.punkt.gueltig", USERS) is None
    assert auth.token_user(secret, f"{encoded}.{'0' * 64}", USERS) is None
    assert auth.token_user(secret, f"!!!.{mac}", USERS) is None
    assert auth.token_user(b"anderer", good, USERS) is None


def test_adresse_muss_in_der_liste_stehen():
    secret = b"testschluessel"
    token = auth.token_for(secret, "wer@anders.example")
    assert auth.token_user(secret, token, USERS) is None
    # Aus der Liste entfernt: sofort abgemeldet.
    anna = auth.token_for(secret, USERS[0])
    assert auth.token_user(secret, anna, USERS[1:]) is None


# -- Nutzerliste aus der Konfiguration ---------------------------------


def test_parse_users():
    assert parse_users("Anna@Example.org, bea@example.org  anna@example.org") == USERS
    assert parse_users("") == []


def test_parse_users_weist_pfadtricks_ab():
    with pytest.raises(ValueError):
        parse_users("../boese@example.org")
    with pytest.raises(ValueError):
        parse_users(".versteckt@example.org")
