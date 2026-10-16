"""The one data path of the Search-fed declarative panels (Stat Cards, Chart).

A declarative panel binds to ONE Search through a ``USES_SEARCH`` edge (the binding the table panel uses,
``tap_web.panel.get_panel_search``), executes it through ``tap_grid.search.execute_search`` with the page's
inputs coerced by the Search's own ``input_schema``, and reads the ``rows`` envelope an aggregating Gryphon
search returns (``req-grid-gryphon-rows``). The outcome is stated, never silent: rows, or the reason there
are none.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelRows:
    """Outcome of running a panel's Search: ``rows`` (possibly empty) or an ``error`` sentence."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def fetch_panel_rows(panel: Panel, request: HttpRequest, *, label: str) -> PanelRows:
    """Execute the Search bound to ``panel`` and return its rows, or the reason there are none.

    ``label`` names the panel kind in the log line only. A Search that RETURNs nodes yields no rows, and
    says so (an error) rather than drawing nothing.
    """
    from tap_web.panel import get_panel_search

    search = get_panel_search(panel)
    if search is None:
        return PanelRows(error="No search linked to this panel.")

    try:
        from tap_grid.search import execute_search, inputs_from_query

        inputs = inputs_from_query(search, request.GET)
        result = execute_search(search, inputs or None, layer="extended")
    except Exception as exc:  # noqa: BLE001
        logger.exception("[3c5e] %s search execution failed for panel %s", label, panel.entity_id)
        return PanelRows(error=f"Search execution failed: {exc}")

    envelope = result["results"] if "results" in result else result
    rows = [r for r in (envelope.get("rows") or []) if isinstance(r, dict)]
    if not rows and envelope.get("nodes"):
        return PanelRows(error="The search returned nodes, not rows: RETURN aliases (for example COUNT(x) AS n).")
    return PanelRows(rows=rows)
