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


_JS = (_STATIC / "js" / "panel-table.js").read_text(encoding="utf-8")
_STAT = (_STATIC / "css" / "stat-cards.css").read_text(encoding="utf-8")
_GRAPH = (Path(__file__).resolve().parents[2] / "tap_viz" / "static" / "tap_viz" / "css" / "panel-graph.css").read_text(
    encoding="utf-8"
)


class TestCellAlignment:
    @pytest.mark.spec("req-web-stdpanel-table-config-25")
    def test_every_built_column_set_is_centred_by_default(self) -> None:
        assert 'if (!col.vertAlign) col.vertAlign = "middle";' in _JS
        assert 'if (!col.hozAlign) col.hozAlign = "left";' in _JS
        assert "return _centred(col);" in _JS  # custom columns
        assert "COMMON_METADATA_COLUMNS.forEach(_centred);" in _JS
        assert "EDGE_COLUMNS.forEach(_centred);" in _JS

    @pytest.mark.spec("req-web-stdpanel-table-config-25")
    def test_long_plain_text_still_ends_in_an_ellipsis(self) -> None:
        body = _rule(".tabulator .tabulator-cell .tap-cell-text")
        for needle in ("min-width: 0", "overflow: hidden", "text-overflow: ellipsis"):
            assert needle in body, needle

    @pytest.mark.spec("req-web-stdpanel-table-config-25")
    def test_the_other_core_tables_centre_vertically(self) -> None:
        assert "border: 0; vertical-align: middle; }" in _STAT
        assert "vertical-align: top" not in _STAT
        assert "vertical-align: top" not in _GRAPH
        assert _GRAPH.count("vertical-align: middle;") >= 2
