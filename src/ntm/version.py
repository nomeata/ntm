"""Woher die angezeigte Revision kommt.

Im Nix-Paket gibt es kein ``.git``: dort schreibt der Build beim Bauen eine
``_build.py`` mit der Revision aus dem Flake (``self.rev`` bzw. ``dirtyRev``).
Läuft die App dagegen aus einem Arbeitsverzeichnis, wird ``.git`` direkt
gelesen – ohne git-Aufruf, es geht nur um zwei Textdateien.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

UNKNOWN = "unbekannt"
REPOSITORY = "https://github.com/nomeata/ntm"


def _from_build() -> str | None:
    try:
        from ._build import REVISION  # type: ignore[attr-defined]
    except ImportError:
        return None
    return REVISION or None


def _from_git() -> str | None:
    root = Path(__file__).resolve().parents[2] / ".git"
    head_file = root / "HEAD"
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head  # abgekoppelter HEAD
    ref = head[4:].strip()
    try:
        return (root / ref).read_text(encoding="utf-8").strip()
    except OSError:
        pass
    try:
        for line in (root / "packed-refs").read_text(encoding="utf-8").splitlines():
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha
    except OSError:
        pass
    return None


@lru_cache(maxsize=1)
def revision() -> str:
    """Kurze Revision des laufenden Standes."""
    found = _from_build() or _from_git()
    if not found:
        return UNKNOWN
    short = found.split("-")[0][:8]
    return f"{short}-dirty" if found.endswith("-dirty") else short


def info() -> dict[str, str | None]:
    """Was die Fußzeile anzeigt: die Revision und wo sie nachzuschlagen ist."""
    current = revision()
    if current == UNKNOWN:
        return {"revision": current, "url": None}
    commit = current.removesuffix("-dirty")
    return {"revision": current, "url": f"{REPOSITORY}/commit/{commit}"}
