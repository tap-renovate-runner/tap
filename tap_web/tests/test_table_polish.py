"""Table panel polish: popovers, cell alignment, plain links, striped rows.

These options live in shipped static CSS and JS, so the tests read the stylesheet and script text (the
schema half is in test_table_panel.py, the pure column logic in js/table_columns.test.mjs). The behaviour
itself was measured in a real browser, light and dark (see the spec's Notes column).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[1] / "static" / "tap_web"
_CSS = (_STATIC / "css" / "tabulator-minimal.css").read_text(encoding="utf-8")
_THEME = (_STATIC / "css" / "theme.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    """The declaration block of the rule whose selector list is exactly `selector`."""
    match = re.search(rf"(?m)^{re.escape(selector)} \{{([^}}]*)\}}", _CSS)
    assert match, f"no rule for {selector}"
    return match.group(1)


class TestPopover:
    @pytest.mark.spec("req-web-stdpanel-table-config-24")
    def test_the_header_popover_takes_surface_ink_and_rule_from_tokens(self) -> None:
        body = _rule(".tabulator-popup-container")
        for needle in ("background: rgb(var(--tap-white))", "color: rgb(var(--tap-slate-900))", "border: 1px solid rgb(var(--tap-slate-400))"):
            assert needle in body, needle
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", body), "no literal colour in the popover rule"

    @pytest.mark.spec("req-web-stdpanel-table-config-24")
    def test_the_sortable_header_hover_is_a_token_not_the_library_grey(self) -> None:
        body = _rule(".tabulator .tabulator-header .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover")
        assert "background: rgb(var(--tap-slate-100))" in body
