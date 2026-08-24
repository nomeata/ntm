"""Datenmodell eines Eintrags."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from . import ages, tags as tags_mod

SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class EntryInput(BaseModel):
    """Was das Formular schickt."""

    title: str = ""
    description: str = ""
    text: str = ""
    age_from: int = ages.AGE_MIN
    age_to: int = ages.AGE_MAX
    tags: list[str] = Field(default_factory=list)
    book: str = ""
    location: str = ""

    @field_validator("title", "description", "text", "book", "location", mode="before")
    @classmethod
    def _clean_str(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip() if not isinstance(value, str) else value.strip()

    @field_validator("age_from", "age_to", mode="before")
    @classmethod
    def _parse_age(cls, value: object) -> int:
        return ages.parse_age(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _clean_tags(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return tags_mod.normalize_tags([str(tag) for tag in value])

    @model_validator(mode="after")
    def _order_ages(self) -> EntryInput:
        if self.age_from > self.age_to:
            self.age_from, self.age_to = self.age_to, self.age_from
        return self

    @field_serializer("age_from", "age_to", when_used="json")
    def _serialize_age(self, value: int) -> int | str:
        return ages.serialize_age(value)


class Entry(EntryInput):
    """Ein gespeicherter Eintrag."""

    schema_version: int = SCHEMA_VERSION
    id: str
    created: datetime = Field(default_factory=_now)
    updated: datetime = Field(default_factory=_now)

    @classmethod
    def create(cls, entry_id: str, data: EntryInput) -> Entry:
        now = _now()
        return cls(
            id=entry_id,
            created=now,
            updated=now,
            **data.model_dump(),
        )

    def updated_with(self, data: EntryInput) -> Entry:
        return Entry(
            id=self.id,
            created=self.created,
            updated=_now(),
            **data.model_dump(),
        )

    def haystack(self) -> tuple[str, str, str]:
        return (self.title, self.description, self.text)
