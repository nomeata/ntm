"""HTTP-API und Auslieferung des Frontends."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ages, auth, render, tags as tags_mod
from .config import Settings
from .models import Entry, EntryInput
from .query import SearchQuery, search
from .store import Store, valid_id

STATIC_DIR = Path(__file__).parent / "static"


class LoginRequest(BaseModel):
    password: str = ""


def _summary(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "title": entry.title,
        "description": entry.description,
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
    store = Store(settings.data_dir)
    app = FastAPI(title="ntm – Therapiematerialien", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.store = store

    async def require_auth(
        authorization: Annotated[str | None, Header()] = None,
    ) -> None:
        if not settings.auth_required:
            return
        token = ""
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not auth.token_valid(token, settings.password):
            raise HTTPException(status_code=401, detail="nicht angemeldet")

    guarded = [Depends(require_auth)]

    # -- Anmeldung -----------------------------------------------------

    @app.get("/api/auth")
    async def auth_info() -> dict[str, bool]:
        return {"required": settings.auth_required}

    @app.post("/api/login")
    async def login(request: LoginRequest) -> dict[str, str]:
        if not settings.auth_required:
            return {"token": ""}
        if not auth.password_valid(request.password, settings.password):
            await asyncio.sleep(0.5)  # bremst stumpfes Durchprobieren
            raise HTTPException(status_code=401, detail="falsches Passwort")
        return {"token": auth.session_token(settings.password)}

    # -- Stammdaten ----------------------------------------------------

    @app.get("/api/meta", dependencies=guarded)
    async def meta() -> dict[str, Any]:
        universe = store.tag_universe()
        books = store.books()
        return {
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
        }

    @app.get("/api/tags/suggest", dependencies=guarded)
    async def suggest_tags(
        q: str = "", limit: int = Query(default=12, ge=1, le=50)
    ) -> dict[str, Any]:
        suggestions = tags_mod.suggest(store.tag_universe(), q, limit=limit)
        return {
            "suggestions": [
                {"tag": item.tag, "count": item.count} for item in suggestions
            ]
        }

    @app.get("/api/books/suggest", dependencies=guarded)
    async def suggest_books(
        q: str = "", limit: int = Query(default=12, ge=1, le=50)
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

    @app.get("/api/search", dependencies=guarded)
    async def do_search(
        q: str = "",
        tag: Annotated[list[str], Query()] = [],
        age: str | None = None,
        limit: int = Query(default=200, ge=1, le=2000),
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

    @app.get("/api/entries/{entry_id}", dependencies=guarded)
    async def get_entry(entry_id: str) -> dict[str, Any]:
        if not valid_id(entry_id):
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        entry = store.get(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        return _detail(entry)

    @app.post("/api/entries", dependencies=guarded, status_code=201)
    async def create_entry(data: EntryInput) -> dict[str, Any]:
        if not data.title.strip():
            raise HTTPException(status_code=422, detail="Titel fehlt")
        return _detail(store.create(data))

    @app.put("/api/entries/{entry_id}", dependencies=guarded)
    async def update_entry(entry_id: str, data: EntryInput) -> dict[str, Any]:
        if not valid_id(entry_id):
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        if not data.title.strip():
            raise HTTPException(status_code=422, detail="Titel fehlt")
        entry = store.update(entry_id, data)
        if entry is None:
            raise HTTPException(status_code=404, detail="unbekannter Eintrag")
        return _detail(entry)

    @app.delete("/api/entries/{entry_id}", dependencies=guarded)
    async def delete_entry(entry_id: str) -> dict[str, bool]:
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
