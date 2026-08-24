"""HTTP-Schnittstelle."""

import pytest
from fastapi.testclient import TestClient

from ntm.app import create_app
from ntm.auth import session_token
from ntm.config import Settings

PASSWORD = "geheim"


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, password=PASSWORD))
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {session_token(PASSWORD)}"})
        yield client


@pytest.fixture
def open_client(tmp_path):
    """Ohne konfiguriertes Passwort ist die App offen (lokales Arbeiten)."""
    app = create_app(Settings(data_dir=tmp_path, password=""))
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
    app = create_app(Settings(data_dir=tmp_path, password=PASSWORD))
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/search").status_code == 401
        assert anonymous.get("/api/meta").status_code == 401
        assert anonymous.post("/api/entries", json={"title": "x"}).status_code == 401


def test_login_liefert_token(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, password=PASSWORD))
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/auth").json() == {"required": True}
        assert anonymous.post("/api/login", json={"password": "falsch"}).status_code == 401
        response = anonymous.post("/api/login", json={"password": PASSWORD})
        assert response.status_code == 200
        token = response.json()["token"]
        assert token == session_token(PASSWORD)
        anonymous.headers.update({"Authorization": f"Bearer {token}"})
        assert anonymous.get("/api/search").status_code == 200


def test_ohne_passwort_ist_die_app_offen(open_client):
    assert open_client.get("/api/auth").json() == {"required": False}
    assert open_client.get("/api/search").status_code == 200


# -- Einträge ----------------------------------------------------------


def test_anlegen_lesen_aendern_loeschen(client):
    entry = create(
        client,
        title="Kasus-Memory",
        description="Memory zu Dativ",
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
