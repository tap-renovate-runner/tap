"""Stat Cards Panel — built-in panel type that renders one metric card per Search row.

The panel binds to ONE Search through a USES_SEARCH edge (the same binding the
table panel uses, ``tap_web.panel.get_panel_search``) and reads the ``rows``
envelope an aggregating Gryphon search returns (req-grid-gryphon-rows): one row
per GROUP BY key combination, or one row when the RETURN is all aggregates.
Every card is one row.

Everything about a card is declared in ``Panel.config`` by FIELD NAME of the
returned row — never by value, never by a node id or tool name
(req-web-stdpanel-statcards-config). Config validates against
``STAT_CARD_CONFIG_SCHEMA``.

Rendering is server-side semantic HTML. The two formatters that depend on the
viewer (``datetime``, ``age``) emit a ``<time>`` element that the shared static
JS finishes in the browser (``localtime.js`` for ``datetime``; ``stat-cards.js``
for ``age``); with no JS the element still reads the exact ISO value.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import jsonschema
from django.core.exceptions import ValidationError

from tap_web.panels.search_rows import fetch_panel_rows

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)

TONES: tuple[str, ...] = ("neutral", "good", "warn", "bad", "muted")
FORMATTERS: tuple[str, ...] = ("text", "number", "integer", "datetime", "age")

_DEFAULT_MAX_CARDS = 24
_DEFAULT_NULL_TEXT = "not observed"
_DEFAULT_MISSING_TEXT = "not returned by the search"
_DEFAULT_BLANK_TEXT = "(empty)"
# Words that carry a tone in text, so colour is never the only signal. `neutral`
# and `muted` carry none: they are the absence of a verdict.
_DEFAULT_TONE_LABELS: dict[str, str] = {"good": "Good", "warn": "Warning", "bad": "Problem"}

_FIELD = {"type": "string", "minLength": 1}
_FORMATTER = {"type": "string", "enum": list(FORMATTERS)}
_TONE = {"type": "string", "enum": list(TONES)}

# JSON Schema for Panel.config on Stat Cards instances. Every property carries a
# description (repo rule: JSON structures describe themselves).
STAT_CARD_CONFIG_SCHEMA: dict[str, Any] = {
    "description": (
        "Config of a Stat Cards panel: how each row of the bound Search's `rows` result becomes one metric card. "
        "Fields are named by the row's RETURN alias; nothing here names a value, node or tool."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["value_field"],
    "properties": {
        "value_field": {
            **_FIELD,
            "description": "Alias of the row field shown as the card's main figure.",
        },
        "value_formatter": {
            **_FORMATTER,
            "description": "How the main figure is formatted: text (default), number, integer, datetime or age.",
        },
        "unit": {
            "type": "string",
            "maxLength": 40,
            "description": "Fixed unit or label printed beside the main figure (for example 'open'). Optional.",
        },
        "title": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120,
            "description": "Fixed card title, used when title_field is absent or the row has no value for it.",
        },
        "title_field": {
            **_FIELD,
            "description": "Alias of the row field shown as the card title (one title per row, e.g. a group key).",
        },
        "lines": {
            "type": "array",
            "maxItems": 12,
            "description": "Secondary label/value lines under the figure, in order.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "field"],
                "description": "One secondary line: a label and the row field it shows.",
                "properties": {
                    "label": {"type": "string", "minLength": 1, "maxLength": 80, "description": "Text label."},
                    "field": {**_FIELD, "description": "Alias of the row field shown."},
                    "formatter": {**_FORMATTER, "description": "Formatter for this line; text by default."},
                },
            },
        },
        "tone": {
            "description": (
                "Card tone. Either a fixed tone name, or {field, map, default}: the tone is chosen by the row "
                "value of `field` through `map`, falling back to `default` (neutral when omitted)."
            ),
            "oneOf": [
                _TONE,
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field", "map"],
                    "description": "Choose the tone from a field's value.",
                    "properties": {
                        "field": {**_FIELD, "description": "Alias of the row field whose value picks the tone."},
                        "map": {
                            "type": "object",
                            "description": "Row value (as text) to tone name.",
                            "additionalProperties": _TONE,
                        },
                        "default": {**_TONE, "description": "Tone for a value the map does not list."},
                    },
                },
            ],
        },
        "tone_labels": {
            "type": "object",
            "description": "Override the words that announce a tone (tone name to text); an empty string shows none.",
            "additionalProperties": {"type": "string", "maxLength": 40},
            "propertyNames": _TONE,
        },
        "empty_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": "Text shown when the Search returns no rows. Default: 'No results.'.",
        },
        "null_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80,
            "description": "Text shown for a field whose value is null (unobserved). Default: 'not observed'.",
        },
        "missing_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80,
            "description": "Text shown when the row has no such field at all (a config/Search mismatch).",
        },
        "blank_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80,
            "description": "Text shown for an empty-string value (observed, but empty).",
        },
        "max_cards": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "description": "Most cards drawn; further rows are counted in a notice, never dropped silently. Default 24.",
        },
        "hide_header": {
            "type": "boolean",
            "description": "When true, omit the panel's name heading above the cards.",
        },
    },
}


def _validate_config(config: dict[str, Any]) -> None:
    """Raise ``ValidationError`` when ``config`` fails ``STAT_CARD_CONFIG_SCHEMA``."""
    try:
        jsonschema.validate(instance=config, schema=STAT_CARD_CONFIG_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ValidationError({"config": [exc.message]}) from exc


def _decimal(value: Any) -> Decimal | None:
    """Return ``value`` as a finite Decimal, or None when it is not a plain number."""
    if isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _parse_instant(value: Any) -> datetime | None:
    """An aware UTC-comparable instant from a datetime or an ISO-8601 string, else None.

    A typed ``DateTimeField`` reaches a Gryphon row as a ``datetime``; a collector's string
    field as text. A naive value is read as UTC, the grid's canonical zone.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def format_cell(row: dict[str, Any], field: str, formatter: str, config: dict[str, Any]) -> dict[str, Any]:
    """Format one row field into a template cell.

    A cell is ``{"kind", "text", ...}`` where kind is ``text`` (plain),
    ``time`` (a localized instant), ``age`` (an elapsed time the browser
    computes) or ``state`` (null / missing / blank, drawn muted so it can never
    pass for a value). The three states are told apart on purpose: a field the
    row does not carry is a config mismatch, null is *unobserved*, and ``""``
    is observed-empty (the grid's null convention).
    """
    if field not in row:
        return {"kind": "state", "state": "missing", "text": config.get("missing_text", _DEFAULT_MISSING_TEXT)}
    value = row[field]
    if value is None:
        return {"kind": "state", "state": "null", "text": config.get("null_text", _DEFAULT_NULL_TEXT)}
    if value == "":
        return {"kind": "state", "state": "blank", "text": config.get("blank_text", _DEFAULT_BLANK_TEXT)}

    if formatter in ("number", "integer"):
        d = _decimal(value)
        if d is None:
            return {"kind": "text", "text": str(value), "title": "not a number"}
        if formatter == "integer":
            return {"kind": "text", "text": f"{int(d.to_integral_value()):,}"}
        whole, _, frac = f"{d:,f}".partition(".")
        frac = frac.rstrip("0")
        return {"kind": "text", "text": f"{whole}.{frac}" if frac else whole}
    if formatter in ("datetime", "age"):
        instant = _parse_instant(value)
        if instant is None:
            return {"kind": "text", "text": str(value), "title": "not a date-time"}
        iso = instant.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {"kind": "time" if formatter == "datetime" else "age", "text": iso, "iso": iso}
    return {"kind": "text", "text": str(value)}


def _tone_for(row: dict[str, Any], tone: Any) -> str:
    if isinstance(tone, str):
        return tone
    if isinstance(tone, dict):
        raw = row.get(tone["field"])
        key = "" if raw is None else str(raw)
        return str(tone["map"].get(key, tone.get("default", "neutral")))
    return "neutral"


def build_cards(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn search rows into template-ready cards, driven only by ``config``."""
    labels = {**_DEFAULT_TONE_LABELS, **(config.get("tone_labels") or {})}
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        title: dict[str, Any] | None = None
        if config.get("title_field"):
            cell = format_cell(row, config["title_field"], "text", config)
            if cell["kind"] == "text":
                title = cell
        if title is None and config.get("title"):
            title = {"kind": "text", "text": config["title"]}
        tone = _tone_for(row, config.get("tone", "neutral"))
        cards.append(
            {
                "index": index,
                "title": title,
                "value": format_cell(row, config["value_field"], config.get("value_formatter", "text"), config),
                "unit": config.get("unit", ""),
                "lines": [
                    {
                        "label": line["label"],
                        "cell": format_cell(row, line["field"], line.get("formatter", "text"), config),
                    }
                    for line in config.get("lines", [])
                ],
                "tone": tone,
                "tone_label": labels.get(tone, ""),
            }
        )
    return cards


class StatCardPanelType:
    """Built-in stat-card panel type descriptor."""

    slug = "stat-cards"
    label = "Stat Cards"
    view = "tap_web/panels/stat_card_panel.html"
    editor_view = ""
    css: list[str] = ["tap_web/css/stat-cards.css"]
    js: list[str] = ["tap_web/js/stat-cards.js"]
    config_defaults: dict[str, Any] = {"max_cards": _DEFAULT_MAX_CARDS}

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        """Execute the bound Search and return the cards (or the reason there are none)."""
        config = {**cls.config_defaults, **(panel.config or {})}
        base: dict[str, Any] = {"cards": [], "cards_error": None, "cards_empty_text": None, "cards_omitted": 0}

        try:
            _validate_config(config)
        except ValidationError as exc:
            return {**base, "cards_error": f"Invalid stat-card config: {'; '.join(exc.messages)}"}

        fetched = fetch_panel_rows(panel, request, label="Stat cards")
        if fetched.error:
            return {**base, "cards_error": fetched.error}
        rows = fetched.rows
        if not rows:
            return {**base, "cards_empty_text": config.get("empty_text", "No results.")}

        limit = config["max_cards"]
        return {**base, "cards": build_cards(rows[:limit], config), "cards_omitted": max(0, len(rows) - limit)}
