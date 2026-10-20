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


class TestPlainLinks:
    @pytest.mark.spec("req-web-stdpanel-table-config-26")
    def test_the_plain_modifier_drops_colour_underline_and_hover_but_keeps_the_focus_ring(self) -> None:
        match = re.search(r"(?m)^\.tabulator \.tap-cell-link--plain,\n(?:.*\n)*?.*:focus-visible \{([^}]*)\}", _CSS)
        assert match, "no plain-link rule"
        assert "color: inherit" in match.group(1) and "text-decoration: none" in match.group(1)
        assert ".tabulator .tap-cell-link--plain:hover" in _CSS
        assert "outline: none" not in _CSS and "outline:none" not in _CSS  # the focus ring stays
        # the plain rule comes after the default link rules, so equal specificity resolves to it
        assert _CSS.index("tap-cell-link--plain,") > _CSS.index(".tabulator .tap-cell-link:focus-visible")

    @pytest.mark.spec("req-web-stdpanel-table-config-26")
    def test_the_three_link_formatters_use_the_class_helper(self) -> None:
        assert 'params && params.style === "plain" ? "tap-cell-link tap-cell-link--plain" : "tap-cell-link"' in _JS
        assert _JS.count("_linkClass(params)") == 3  # externalLink, link, linkList
        assert "externalLink: function (cell, params)" in _JS

    @pytest.mark.spec("req-web-stdpanel-table-config-26")
    def test_style_is_a_described_enum_in_the_schema(self) -> None:
        from tap_web.panels.table_panel import TABLE_CONFIG_SCHEMA, _validate_table_config

        fp = TABLE_CONFIG_SCHEMA["$defs"]["column"]["properties"]["formatter_params"]
        assert fp["description"] and fp["properties"]["style"]["description"]
        assert fp["properties"]["style"]["enum"] == ["default", "plain"]
        col = {"field": "a", "title": "A", "formatter": "link", "formatter_params": {"style": "plain", "external": False}}
        _validate_table_config({"columns": [col]})
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_table_config({"columns": [{**col, "formatter_params": {"style": "loud"}}]})
