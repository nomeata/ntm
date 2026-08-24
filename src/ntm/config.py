"""Konfiguration – ausschließlich über Umgebungsvariablen bzw. CLI-Argumente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path("./data")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8123


@dataclass
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    password: str = ""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def auth_required(self) -> bool:
        return bool(self.password)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        password = env.get("NTM_PASSWORD", "")
        password_file = env.get("NTM_PASSWORD_FILE", "")
        if not password and password_file:
            password = Path(password_file).read_text(encoding="utf-8").strip()
        return cls(
            data_dir=Path(env.get("NTM_DATA_DIR", str(DEFAULT_DATA_DIR))),
            password=password,
            host=env.get("NTM_HOST", DEFAULT_HOST),
            port=int(env.get("NTM_PORT", DEFAULT_PORT)),
        )
