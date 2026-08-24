"""Markdown → HTML.

Gerendert wird serverseitig, damit das Frontend ohne Build-Schritt und ohne
JS-Abhängigkeiten auskommt.
"""

from __future__ import annotations

from functools import lru_cache

from markdown_it import MarkdownIt

try:  # nur für das Verlinken nackter URLs
    import linkify_it  # noqa: F401

    _LINKIFY = True
except ImportError:  # pragma: no cover – Nebensache, kein Grund zu scheitern
    _LINKIFY = False

_md = MarkdownIt("commonmark", {"linkify": _LINKIFY, "breaks": True})
_md.enable("table").enable("strikethrough")
if _LINKIFY:
    _md.enable("linkify")


@lru_cache(maxsize=512)
def to_html(markdown: str) -> str:
    if not markdown.strip():
        return ""
    return _md.render(markdown)
