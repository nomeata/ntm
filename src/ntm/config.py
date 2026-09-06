"""Konfiguration – ausschließlich über Umgebungsvariablen bzw. CLI-Argumente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_DIR = Path("./data")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8123
DEFAULT_SENDMAIL = "sendmail"


def parse_users(raw: str) -> list[str]:
    """Adressliste aus der Konfiguration: durch Komma oder Leerraum getrennt.

    Kleingeschrieben, Duplikate entfernt, Reihenfolge erhalten – die *erste*
    Adresse bekommt bei der Migration den Altbestand zugewiesen.
    """
    seen: list[str] = []
    for chunk in raw.replace(",", " ").split():
        email = chunk.strip().lower()
        if not email or email in seen:
            continue
        if "/" in email or email.startswith("."):
            raise ValueError(f"unbrauchbare E-Mail-Adresse: {email!r}")
        seen.append(email)
    return seen


@dataclass
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    users: list[str] = field(default_factory=list)
    mail_from: str = ""
    sendmail: str = DEFAULT_SENDMAIL
    base_url: str = ""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def auth_required(self) -> bool:
        return bool(self.users)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        return cls(
            data_dir=Path(env.get("NTM_DATA_DIR", str(DEFAULT_DATA_DIR))),
            users=parse_users(env.get("NTM_USERS", "")),
            mail_from=env.get("NTM_MAIL_FROM", ""),
            sendmail=env.get("NTM_SENDMAIL", DEFAULT_SENDMAIL),
            base_url=env.get("NTM_BASE_URL", "").rstrip("/"),
            host=env.get("NTM_HOST", DEFAULT_HOST),
            port=int(env.get("NTM_PORT", DEFAULT_PORT)),
        )
