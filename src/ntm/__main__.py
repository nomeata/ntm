"""Startpunkt: ``ntm --data-dir ./data --port 8123``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from .app import create_app
from .config import Settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ntm", description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="Verzeichnis der JSON-Dateien")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    settings = Settings.from_env()
    if args.data_dir:
        settings.data_dir = args.data_dir
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port

    if not settings.auth_required:
        logging.warning(
            "Keine Nutzerliste gesetzt (NTM_USERS) – die App ist ungeschützt."
        )
    elif not settings.mail_from:
        logging.warning(
            "NTM_MAIL_FROM ist leer – Login-Mails kommen ohne Absender."
        )
    logging.info("Datenverzeichnis: %s", settings.data_dir.resolve())
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
