"""Anmeldung per magic link – keine Passwörter.

Beim ersten Start erzeugt der Server einen zufälligen Schlüssel in
``<Datenverzeichnis>/.secret``.  Das Token einer Nutzerin ist ein HMAC über
ihre Adresse mit diesem Schlüssel: zustandslos prüfbar, überlebt Neustarts,
läuft bewusst nie ab.  Gültig ist es nur, solange die Adresse auch in der
konfigurierten Nutzerliste steht – wer daraus entfernt wird, ist sofort
abgemeldet; das Löschen von ``.secret`` meldet alle ab.

Das Token trägt die Adresse (base64) in sich, damit der Server weiß, wessen
Daten er zeigen soll: ``<base64(email)>.<hmac>``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

_PURPOSE = b"ntm/login/v1:"

SECRET_FILE = ".secret"


def load_secret(data_dir: Path) -> bytes:
    """Liest den Schlüssel oder legt ihn an (nur für den Dienst lesbar)."""
    path = data_dir / SECRET_FILE
    try:
        existing = path.read_bytes().strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(32).encode("ascii")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(secret + b"\n")
    return secret


def _b64(email: str) -> str:
    return base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")


def _mac(secret: bytes, email: str) -> str:
    return hmac.new(secret, _PURPOSE + email.encode("utf-8"), hashlib.sha256).hexdigest()


def token_for(secret: bytes, email: str) -> str:
    email = email.strip().lower()
    return f"{_b64(email)}.{_mac(secret, email)}"


def token_user(secret: bytes, token: str, users: list[str]) -> str | None:
    """Die Adresse zum Token – oder None, wenn es nicht (mehr) gilt."""
    encoded, _, mac = (token or "").partition(".")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        email = base64.urlsafe_b64decode(padded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    email = email.strip().lower()
    if email not in users:
        return None
    if not hmac.compare_digest(mac, _mac(secret, email)):
        return None
    return email
