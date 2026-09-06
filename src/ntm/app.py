"""HTTP-API und Auslieferung des Frontends."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ages, auth, mail, render, tags as tags_mod, version
from .config import Settings
from .models import Entry, EntryInput
from .query import SearchQuery, search
from .store import Store, migrate_legacy, valid_id

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Frühestens alle 60 s eine weitere Mail an dieselbe Adresse – der Endpoint
# ist unauthentifiziert und soll kein Mail-Katapult sein.
MAIL_COOLDOWN = 60.0


class LoginRequest(BaseModel):
    email: str = ""


def _summary(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "title": entry.title,
        "tags": entry.tags,
        "age_from": ages.serialize_age(entry.age_from),
        "age_to": ages.serialize_age(entry.age_to),
        "age_label": ages.range_label(entry.age_from, entry.age_to),
        "book": entry.book,
        "location": entry.location,
        "has_text": bool(entry.text.strip()),
    }


def _detail(entry: Entry) -> dict[str, Any]:
    data = entry.model_dump(mode="json")
    data["age_label"] = ages.range_label(entry.age_from, entry.age_to)
    data["text_html"] = render.to_html(entry.text)
    return data


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="ntm – Therapiematerialien", docs_url=None, redoc_url=None)
    app.state.settings = settings

    secret = b""
    if settings.auth_required:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        secret = auth.load_secret(settings.data_dir)
        migrate_legacy(settings.data_dir, settings.users[0])

    # Ein Store pro Nutzerin (bzw. einer im offenen Modus), erst bei Bedarf.
    stores: dict[str | None, Store] = {}

    def store_for(user: str | None) -> Store:
        if user not in stores:
            directory = settings.data_dir if user is None else settings.data_dir / user
            stores[user] = Store(directory)
        return stores[user]

    async def current_user(
        authorization: Annotated[str | None, Header()] = None,
    ) -> str | None:
        if not settings.auth_required:
            return None
        token = ""
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        user = auth.token_user(secret, token, settings.users)
        if user is None:
            raise HTTPException(status_code=401, detail="nicht angemeldet")
        return user

    def current_store(user: str | None = Depends(current_user)) -> Store:
        return store_for(user)

    # -- Anmeldung -----------------------------------------------------

    last_mail: dict[str, float] = {}

    def base_url(request: Request) -> str:
        if settings.base_url:
            return settings.base_url
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        return f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}"

    @app.get("/api/auth")
    async def auth_info() -> dict[str, bool]:
        return {"required": settings.auth_required}

    @app.post("/api/login")
    async def login(request: Request, data: LoginRequest) -> dict[str, Any]:
        # Die Antwort ist absichtlich immer dieselbe – ob eine Adresse zur
        # Nutzerliste gehört, lässt sich von außen nicht abfragen.
        generic: dict[str, Any] = {"sent": settings.auth_required}
        if not settings.auth_required:
            return generic
        email = data.email.strip().lower()
        if email not in settings.users:
            return generic
        now = time.monotonic()
        previous = last_mail.get(email)
        if previous is not None and now - previous < MAIL_COOLDOWN:
            return generic
        last_mail[email] = now
        link = f"{base_url(request)}/#login={auth.token_for(secret, email)}"
        message = mail.login_mail(settings.mail_from, email, link)
        try:
            await asyncio.to_thread(mail.send, settings.sendmail, message)
        except Exception:
            log.exception("Login-Mail an %s fehlgeschlagen", email)
            last_mail.pop(email, None)  # ein neuer Versuch darf sofort senden
        return generic

    # -- Stammdaten ----------------------------------------------------

    @app.get("/api/meta")
    async def meta(
        user: str | None = Depends(current_user),
        store: Store = Depends(current_store),
    ) -> dict[str, Any]:
        universe = store.tag_universe()
        books = store.books()
        return {
            "user": user,
            "tags": [
                {"tag": tag, "count": count}
                for tag, count in sorted(
                    universe.items(), key=lambda item: item[0].casefold()
                )
            ],
            "books": [
                {"book": book, "count": count}
                for book, count in sorted(
                    books.items(), key=lambda item: (-item[1], item[0].casefold())
                )
            ],
            "ages": [
                {"value": ages.serialize_age(value), "label": ages.age_label(value)}
                for value in ages.axis()
            ],
            "entries": len(store.all()),
            "build": version.info(),
        }

    @app.get("/api/tags/suggest")
    async def suggest_tags(
        q: str = "",
        limit: int = Query(default=12, ge=1, le=50),
        store: Store = Depends(current_store),
    ) -> dict[str, Any]:
        suggestions = tags_mod.suggest(store.tag_universe(), q, limit=limit)
        return {
            "suggestions": [
                {"tag": item.tag, "count": item.count} for item in suggestions
            ]
        }

    @app.get("/api/books/suggest")
    async def suggest_books(
        q: str = "",
        limit: int = Query(default=12, ge=1, le=50),
        store: Store = Depends(current_store),
    ) -> dict[str, Any]:
        from . import text as text_mod

        books = store.books()
        scored = []
        for book, count in books.items():
            folded = text_mod.fold(book)
            if q.strip() and not text_mod.contains(folded, q.strip()):
                continue
            prefix = folded[0].startswith(text_mod.fold(q.strip())[0])
            scored.append((0 if prefix else 1, -count, book.casefold(), book, count))
        scored.sort()
        return {
            "suggestions": [
                {"book": book, "count": count} for _, _, _, book, count in scored[:limit]
            ]
        }

    # -- Suche ---------------------------------------------------------

    @app.get("/api/search")
    async def do_search(
        q: str = "",
        tag: Annotated[list[str], Query()] = [],
        age: str | None = None,
        limit: int = Query(default=200, ge=1, le=2000),
        store: Store = Depends(current_store),
    ) -> dict[str, Any]:
        try:
            wanted_age = ages.parse_age(age) if age not in (None, "") else None
        except ValueError:
            raise HTTPException(status_code=422, detail="ungültiges Alter") from None
        query = SearchQuery(
            q=q,
            tags=[t for t in (tags_mod.normalize_tag(item) for item in tag) if t],
            age=wanted_age,
        )
        hits = search(store.all(), query)
        return {
            "total": len(hits),
            "entries": [_summary(entry) for entry in hits[:limit]],
        }

    # -- Einträge ------------------------------------------------------

    @app.get("/api/entries/{entry_id}")
    async def get_entry(
        entry_id: str, store: Store = Depends(current_store)
    ) -> dict[str, Any]:
        if not valid_id(entry_id):
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        entry = store.get(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        return _detail(entry)

    @app.post("/api/entries", status_code=201)
    async def create_entry(
        data: EntryInput, store: Store = Depends(current_store)
    ) -> dict[str, Any]:
        if not data.title.strip():
            raise HTTPException(status_code=422, detail="Titel fehlt")
        return _detail(store.create(data))

    @app.put("/api/entries/{entry_id}")
    async def update_entry(
        entry_id: str, data: EntryInput, store: Store = Depends(current_store)
    ) -> dict[str, Any]:
        if not valid_id(entry_id):
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        if not data.title.strip():
            raise HTTPException(status_code=422, detail="Titel fehlt")
        entry = store.update(entry_id, data)
        if entry is None:
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        return _detail(entry)

    @app.delete("/api/entries/{entry_id}")
    async def delete_entry(
        entry_id: str, store: Store = Depends(current_store)
    ) -> dict[str, bool]:
        if not valid_id(entry_id) or not store.delete(entry_id):
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        return {"deleted": True}

    # -- Frontend ------------------------------------------------------

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
        )

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc: Exception) -> Any:
        # Alles außerhalb von /api und /static gehört dem Frontend-Router.
        if not request.url.path.startswith(("/api", "/static")):
            return FileResponse(
                STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
            )
        detail = getattr(exc, "detail", "not found")
        return JSONResponse({"detail": detail}, status_code=404)

    return app


def app_from_env() -> FastAPI:
    return create_app(Settings.from_env())
