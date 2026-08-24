"""Bewusst minimale Authentifizierung: ein Passwort, eine Nutzerin.

Aus dem Passwort wird deterministisch ein Token abgeleitet.  Damit braucht der
Server keinen Session-Speicher, ein Neustart wirft niemanden hinaus, und im
Local Storage des Browsers liegt nicht das Passwort selbst.

Das Passwort geht beim Login im Klartext über die Leitung – die App gehört
deshalb hinter TLS (siehe README).
"""

from __future__ import annotations

import hashlib
import hmac

_PURPOSE = b"ntm/session/v1"


def session_token(password: str) -> str:
    return hmac.new(_PURPOSE, password.encode("utf-8"), hashlib.sha256).hexdigest()


def token_valid(token: str, password: str) -> bool:
    return hmac.compare_digest(token or "", session_token(password))


def password_valid(given: str, password: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256((given or "").encode("utf-8")).digest(),
        hashlib.sha256(password.encode("utf-8")).digest(),
    )
