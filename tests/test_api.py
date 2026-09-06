"""HTTP-Schnittstelle."""

import email
import email.policy
import re

import pytest
from fastapi.testclient import TestClient

from ntm import auth
from ntm.app import create_app
from ntm.config import Settings

USER = "anna@example.org"
OTHER = "bea@example.org"


def make_settings(data_dir, **kwargs):
    values = dict(
        data_dir=data_dir,
        users=[USER, OTHER],
        mail_from="ntm@example.org",
        base_url="https://ntm.example.org",
    )
    values.update(kwargs)
    return Settings(**values)


def bearer(data_dir, email_address=USER):
    token = auth.token_for(auth.load_secret(data_dir), email_address)
    return {"Authorization": f"Bearer {token}"}


def fake_sendmail(tmp_path):
    """Ein sendmail-Ersatz: Argumente und Mail landen in Dateien."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    script = tmp_path / "sendmail"
    script.write_text(
        f'#!/bin/sh\necho "$@" > "{outbox}/$$.args"\ncat > "{outbox}/$$.eml"\n'
    )
    script.chmod(0o755)
    return script, outbox


def sent_mails(outbox):
    return [
        email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
        for path in sorted(outbox.glob("*.eml"))
    ]


@pytest.fixture
def client(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers.update(bearer(tmp_path))
        yield client


@pytest.fixture
def open_client(tmp_path):
    """Ohne konfigurierte Nutzerliste ist die App offen (lokales Arbeiten)."""
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        yield client


def create(client, **kwargs):
    data = {"title": "Titel", "age_from": 5, "age_to": 21}
    data.update(kwargs)
    response = client.post("/api/entries", json=data)
    assert response.status_code == 201, response.text
    return response.json()


# -- Anmeldung ---------------------------------------------------------


def test_ohne_token_kein_zugriff(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/search").status_code == 401
        assert anonymous.get("/api/meta").status_code == 401
        assert anonymous.post("/api/entries", json={"title": "x"}).status_code == 401


def test_login_verschickt_magic_link(tmp_path):
    script, outbox = fake_sendmail(tmp_path)
    data_dir = tmp_path / "data"
    app = create_app(make_settings(data_dir, sendmail=str(script)))
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/auth").json() == {"required": True}
        # Groß-/Kleinschreibung und Leerraum sind egal.
        response = anonymous.post("/api/login", json={"email": " Anna@Example.org "})
        assert response.json() == {"sent": True}
        (args,) = outbox.glob("*.args")
        assert args.read_text().strip() == USER
        (message,) = sent_mails(outbox)
        assert message["To"] == USER
        assert message["From"] == "ntm@example.org"
        link = re.search(r"https://ntm\.example\.org/#login=(\S+)", message.get_content())
        assert link, message.get_content()
        anonymous.headers.update({"Authorization": f"Bearer {link.group(1)}"})
        meta = anonymous.get("/api/meta")
        assert meta.status_code == 200
        assert meta.json()["user"] == USER


def test_unbekannte_adresse_gleiche_antwort_keine_mail(tmp_path):
    script, outbox = fake_sendmail(tmp_path)
    app = create_app(make_settings(tmp_path / "data", sendmail=str(script)))
    with TestClient(app) as anonymous:
        response = anonymous.post("/api/login", json={"email": "wer@anders.example"})
        assert response.json() == {"sent": True}  # verrät die Liste nicht
        assert sent_mails(outbox) == []


def test_mail_cooldown(tmp_path):
    script, outbox = fake_sendmail(tmp_path)
    app = create_app(make_settings(tmp_path / "data", sendmail=str(script)))
    with TestClient(app) as anonymous:
        for _ in range(3):
            anonymous.post("/api/login", json={"email": USER})
        assert len(sent_mails(outbox)) == 1


def test_kaputtes_token_ist_401(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as anonymous:
        for token in ["quatsch", "cXVhdHNjaA.abc", ""]:
            anonymous.headers.update({"Authorization": f"Bearer {token}"})
            assert anonymous.get("/api/meta").status_code == 401


def test_entfernte_nutzerin_ist_abgemeldet(tmp_path):
    headers = bearer(tmp_path)
    app = create_app(make_settings(tmp_path, users=[OTHER]))
    with TestClient(app) as client:
        assert client.get("/api/meta", headers=headers).status_code == 401


def test_ohne_nutzerliste_ist_die_app_offen(open_client):
    assert open_client.get("/api/auth").json() == {"required": False}
    assert open_client.get("/api/search").status_code == 200
    assert open_client.get("/api/meta").json()["user"] is None
    assert open_client.post("/api/login", json={"email": "x@y"}).json() == {"sent": False}


def test_nutzerinnen_sind_getrennt(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers.update(bearer(tmp_path, USER))
        create(client, title="Annas Eintrag")
        assert client.get("/api/meta").json()["entries"] == 1

        client.headers.update(bearer(tmp_path, OTHER))
        assert client.get("/api/meta").json()["user"] == OTHER
        assert client.get("/api/meta").json()["entries"] == 0
        assert client.get("/api/search").json()["total"] == 0


# -- Einträge ----------------------------------------------------------


def test_anlegen_lesen_aendern_loeschen(client):
    entry = create(
        client,
        title="Kasus-Memory",
        text="# Ablauf\n\nKarten mischen.",
        tags=["Sprache/Grammatik/Kasus"],
        book="Sprachförderung konkret",
        location="S. 45",
        age_from=7,
        age_to=12,
    )
    assert entry["age_label"] == "7–12"
    assert "<h1>Ablauf</h1>" in entry["text_html"]

    fetched = client.get(f"/api/entries/{entry['id']}").json()
    assert fetched["title"] == "Kasus-Memory"
    assert fetched["tags"] == ["Sprache/Grammatik/Kasus"]

    updated = client.put(
        f"/api/entries/{entry['id']}",
        json={**fetched, "title": "Kasus-Memory (neu)", "age_to": "Eltern"},
    )
    assert updated.status_code == 200
    assert updated.json()["age_to"] == "Eltern"
    assert updated.json()["age_label"] == "7–Eltern"

    assert client.delete(f"/api/entries/{entry['id']}").status_code == 200
    assert client.get(f"/api/entries/{entry['id']}").status_code == 404


def test_titel_ist_pflicht(client):
    assert client.post("/api/entries", json={"title": "   "}).status_code == 422


def test_unbekannte_id_ist_404(client):
    assert client.get("/api/entries/gibtsnicht").status_code == 404
    assert client.put("/api/entries/gibtsnicht", json={"title": "x"}).status_code == 404
    assert client.delete("/api/entries/gibtsnicht").status_code == 404


def test_pfadtricks_bei_der_id_werden_abgewiesen(client):
    assert client.get("/api/entries/..%2F..%2Fetc%2Fpasswd").status_code == 404


# -- Suche -------------------------------------------------------------


def test_suche_kombiniert_filter(client):
    create(client, title="Kasus-Memory", tags=["Sprache/Grammatik/Kasus"], age_from=7, age_to=12)
    create(client, title="Wortschatzkiste", tags=["Sprache/Wortschatz"], age_from=5, age_to=9)
    create(client, title="Elternbrief", tags=["Mit Eltern"], age_from="Eltern", age_to="Eltern")

    def titles(**params):
        response = client.get("/api/search", params=params)
        assert response.status_code == 200
        return [entry["title"] for entry in response.json()["entries"]]

    assert titles() == ["Elternbrief", "Kasus-Memory", "Wortschatzkiste"]
    assert titles(q="memory") == ["Kasus-Memory"]
    assert titles(tag="Sprache") == ["Kasus-Memory", "Wortschatzkiste"]
    assert titles(tag=["Sprache", "Sprache/Wortschatz"]) == ["Wortschatzkiste"]
    assert titles(age=8) == ["Kasus-Memory", "Wortschatzkiste"]
    assert titles(age="Eltern") == ["Elternbrief"]
    assert titles(age=8, tag="Sprache/Grammatik") == ["Kasus-Memory"]


def test_suche_meldet_gesamtzahl(client):
    for index in range(3):
        create(client, title=f"Eintrag {index}")
    data = client.get("/api/search", params={"limit": 2}).json()
    assert data["total"] == 3
    assert len(data["entries"]) == 2


def test_ungueltiges_alter_ist_422(client):
    assert client.get("/api/search", params={"age": "vier"}).status_code == 422


# -- Stammdaten --------------------------------------------------------


def test_meta_liefert_tags_buecher_und_altersachse(client):
    create(client, tags=["Sprache/Grammatik/Kasus"], book="Buch A")
    create(client, tags=["Sprache/Wortschatz"], book="Buch A")
    meta = client.get("/api/meta").json()
    tags = {item["tag"]: item["count"] for item in meta["tags"]}
    assert tags["Sprache"] == 2
    assert tags["Sprache/Grammatik/Kasus"] == 1
    assert meta["books"][0] == {"book": "Buch A", "count": 2}
    assert meta["ages"][0] == {"value": 5, "label": "5"}
    assert meta["ages"][-1] == {"value": "Eltern", "label": "Eltern"}
    assert meta["entries"] == 2
    build = meta["build"]
    assert build["revision"]  # aus dem Flake, aus .git, sonst "unbekannt"
    assert build["url"] is None or build["url"].startswith("https://github.com/")


def test_tag_typeahead(client):
    create(client, tags=["Sprache/Grammatik/Kasus"])
    create(client, tags=["Motorik/Grafomotorik"])
    found = client.get("/api/tags/suggest", params={"q": "motorik"}).json()["suggestions"]
    assert [item["tag"] for item in found][:2] == ["Motorik", "Motorik/Grafomotorik"]


def test_buch_typeahead(client):
    create(client, book="Sprachförderung konkret")
    create(client, book="digital")
    found = client.get("/api/books/suggest", params={"q": "sprach"}).json()["suggestions"]
    assert [item["book"] for item in found] == ["Sprachförderung konkret"]


# -- Frontend ----------------------------------------------------------


def test_frontend_wird_ausgeliefert(open_client):
    response = open_client.get("/")
    assert response.status_code == 200
    assert "<div id=\"app\"" in response.text
    assert open_client.get("/static/app.js").status_code == 200


def test_unbekannte_seite_liefert_das_frontend(open_client):
    assert open_client.get("/irgendwas").status_code == 200


def test_unbekannte_api_route_bleibt_404(open_client):
    response = open_client.get("/api/gibtsnicht")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
