"""Anzeige des Programmstands."""

import pytest

from ntm import version


@pytest.fixture(autouse=True)
def _no_cache():
    version.revision.cache_clear()
    yield
    version.revision.cache_clear()


def test_revision_kommt_aus_dem_build(monkeypatch):
    monkeypatch.setattr(version, "_from_build", lambda: "0123456789abcdef" * 2)
    assert version.revision() == "01234567"


def test_build_schlaegt_git(monkeypatch):
    monkeypatch.setattr(version, "_from_build", lambda: "aaaaaaaaaaaa")
    monkeypatch.setattr(version, "_from_git", lambda: "bbbbbbbbbbbb")
    assert version.revision() == "aaaaaaaa"


def test_ohne_beides_unbekannt(monkeypatch):
    monkeypatch.setattr(version, "_from_build", lambda: None)
    monkeypatch.setattr(version, "_from_git", lambda: None)
    assert version.revision() == version.UNKNOWN
    assert version.info() == {"revision": version.UNKNOWN, "url": None}


def test_link_zeigt_auf_den_commit(monkeypatch):
    monkeypatch.setattr(version, "revision", lambda: "abc12345")
    assert version.info() == {
        "revision": "abc12345",
        "url": f"{version.REPOSITORY}/commit/abc12345",
    }


def test_dirty_bleibt_sichtbar_aber_der_link_zeigt_auf_den_commit(monkeypatch):
    monkeypatch.setattr(version, "_from_build", lambda: "abc12345def-dirty")
    assert version.revision() == "abc12345-dirty"
    assert version.info()["url"] == f"{version.REPOSITORY}/commit/abc12345"
