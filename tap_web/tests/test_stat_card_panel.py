"""Tests for the Stat Cards built-in panel type (spec-web-panels-standard, req-web-stdpanel-statcards).

The view tests seed real grid rows, bind a real aggregating Gryphon search and read the fragment the
panel endpoint serves, so the assertions are on what the browser receives. The browser-side finish
(``stat-cards.js`` age text) is proven in a real browser, not here: the repo has no JS test runner.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from tap.pytest_harness import make_admin_client
from tap_web.models import Panel
from tap_web.panels.stat_card_panel import (
    STAT_CARD_CONFIG_SCHEMA,
    StatCardPanelType,
    _validate_config,
    build_cards,
    format_cell,
)

_COUNT_BY_SOURCE = [
    "MATCH (a:grid_fixtures__constrained_source)-[e:CONSTRAINED_LINK__grid_fixtures]->"
    "(b:grid_fixtures__constrained_target)",
    "RETURN a.name AS source, COUNT(b) AS n",
]
_COUNT_ALL = [
    "MATCH (a:grid_fixtures__constrained_source)-[e:CONSTRAINED_LINK__grid_fixtures]->"
    "(b:grid_fixtures__constrained_target)",
    "RETURN COUNT(b) AS n",
]


def _panel(config: dict[str, Any]) -> Panel:
    panel: Panel = Panel.objects.create(
        slug="stat-cards", name="Test Cards", view=StatCardPanelType.view, editor_view="", config=config
    )
    return panel


def _bind(panel: Panel, query: list[str]) -> None:
    from tap_grid.models import Edge, Search

    search = Search.objects.create(name="Cards", search_type="gryphon", root="node", definition={"query": query})
    Edge.objects.create(from_entity=panel.entity, to_entity=search.entity, edge_type="USES_SEARCH")


def _seed(links: dict[str, int]) -> None:
    """Create each named source with N outgoing links to fresh targets."""
    from tap_grid.caller_context import CallerContext, get_caller_context, set_caller_context
    from tap_grid.models import Edge, Entity

    ctx = get_caller_context()
    assert ctx is not None
    set_caller_context(CallerContext(user=ctx.user, batch_id=str(uuid.uuid4())))
    for name, n in links.items():
        src = Entity.objects.create(entity_type="grid_fixtures__constrained_source", name=name)
        for i in range(n):
            tgt = Entity.objects.create(entity_type="grid_fixtures__constrained_target", name=f"{name}/{i}")
            Edge.objects.create(
                entity=Entity.objects.create(entity_type="edge"),
                from_entity=src,
                to_entity=tgt,
                edge_type="CONSTRAINED_LINK__grid_fixtures",
            )


def _get(panel: Panel) -> str:
    response = make_admin_client(username=f"cards-{uuid.uuid4().hex[:8]}").get(
        f"/panel/{panel.slug}--{panel.entity_id}/"
    )
    assert response.status_code == 200
    return str(response.content.decode())


# ---------------------------------------------------------------------------
# req-web-stdpanel-statcards-type
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegistration:
    @pytest.mark.spec("req-web-stdpanel-statcards-type-1")
    def test_registered_under_its_slug(self, django_db_setup):  # noqa: ARG002
        from tap_web.registry import panel_type_registry

        found = [
            scope[StatCardPanelType.slug]
            for scope in panel_type_registry.all().values()
            if StatCardPanelType.slug in scope
        ]
        assert found == [StatCardPanelType]

    @pytest.mark.spec("req-web-stdpanel-statcards-type-2")
    def test_declares_its_own_assets(self):
        assert StatCardPanelType.css == ["tap_web/css/stat-cards.css"]
        assert StatCardPanelType.js == ["tap_web/js/stat-cards.js"]
        assert StatCardPanelType.view == "tap_web/panels/stat_card_panel.html"

    @pytest.mark.spec("req-web-stdpanel-statcards-type-2")
    def test_the_assets_exist_in_static(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "static"
        for path in (*StatCardPanelType.css, *StatCardPanelType.js):
            assert (root / path).is_file(), path

    @pytest.mark.spec("req-web-stdpanel-statcards-type-3")
    def test_defaults_are_valid_once_a_value_field_is_given(self):
        _validate_config({**StatCardPanelType.config_defaults, "value_field": "n"})
        assert StatCardPanelType.config_defaults == {"max_cards": 24}


# ---------------------------------------------------------------------------
# req-web-stdpanel-statcards-config
# ---------------------------------------------------------------------------


def _every_schema_node(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _every_schema_node(v)
    elif isinstance(node, list):
        for v in node:
            yield from _every_schema_node(v)


class TestConfigSchema:
    @pytest.mark.spec("req-web-stdpanel-statcards-config-1")
    def test_value_field_is_required(self):
        with pytest.raises(ValidationError):
            _validate_config({"title": "x"})

    @pytest.mark.spec("req-web-stdpanel-statcards-config-1")
    def test_undeclared_keys_are_rejected(self):
        with pytest.raises(ValidationError):
            _validate_config({"value_field": "n", "colour": "red"})

    @pytest.mark.spec("req-web-stdpanel-statcards-config-2")
    def test_a_full_config_passes(self):
        _validate_config(
            {
                "value_field": "n",
                "value_formatter": "integer",
                "unit": "open",
                "title_field": "source",
                "title": "Fallback",
                "lines": [{"label": "Last report", "field": "seen", "formatter": "datetime"}],
                "tone": {"field": "state", "map": {"red": "bad"}, "default": "good"},
                "tone_labels": {"bad": "Failing"},
                "empty_text": "Nothing",
                "null_text": "unknown",
                "missing_text": "no field",
                "blank_text": "none",
                "max_cards": 5,
                "hide_header": True,
            }
        )

    @pytest.mark.spec("req-web-stdpanel-statcards-config-2")
    @pytest.mark.parametrize("tone", ["neutral", "good", "warn", "bad", "muted"])
    def test_fixed_tones_are_the_five_names(self, tone):
        _validate_config({"value_field": "n", "tone": tone})

    @pytest.mark.spec("req-web-stdpanel-statcards-config-2")
    @pytest.mark.parametrize(
        "bad",
        [
            {"value_formatter": "currency"},
            {"tone": "purple"},
            {"tone": {"field": "s", "map": {"x": "purple"}}},
            {"tone": {"field": "s"}},
            {"lines": [{"label": "L"}]},
            {"lines": [{"label": "L", "field": "f", "formatter": "nope"}]},
            {"max_cards": 0},
            {"max_cards": 500},
            {"tone_labels": {"purple": "x"}},
        ],
    )
    def test_malformed_config_is_rejected(self, bad):
        with pytest.raises(ValidationError):
            _validate_config({"value_field": "n", **bad})

    @pytest.mark.spec("req-web-stdpanel-statcards-config-3")
    def test_every_schema_entry_has_a_description(self):
        """Repo rule: a JSON structure describes itself, at the top and at each entry."""
        assert STAT_CARD_CONFIG_SCHEMA["description"]
        for prop in STAT_CARD_CONFIG_SCHEMA["properties"].values():
            assert prop.get("description"), prop
        lines = STAT_CARD_CONFIG_SCHEMA["properties"]["lines"]
        assert lines["items"]["description"]
        for prop in lines["items"]["properties"].values():
            assert prop.get("description"), prop
        tone = STAT_CARD_CONFIG_SCHEMA["properties"]["tone"]["oneOf"][1]
        assert tone["description"]
        for prop in tone["properties"].values():
            assert prop.get("description"), prop

    @pytest.mark.spec("req-web-stdpanel-statcards-config-4")
    def test_the_schema_names_no_value_node_or_tool(self):
        """Config names row FIELDS only; the schema carries no enumerated domain value."""
        enums = [n["enum"] for n in _every_schema_node(STAT_CARD_CONFIG_SCHEMA) if "enum" in n]
        allowed = {"text", "number", "integer", "datetime", "age", "neutral", "good", "warn", "bad", "muted"}
        assert {v for e in enums for v in e} <= allowed


# ---------------------------------------------------------------------------
# req-web-stdpanel-statcards-format
# ---------------------------------------------------------------------------


class TestFormatCell:
    @pytest.mark.spec("req-web-stdpanel-statcards-format-1")
    @pytest.mark.parametrize(
        ("value", "formatter", "text"),
        [
            (9.8, "number", "9.8"),
            (20, "number", "20"),
            (1234567.5, "number", "1,234,567.5"),
            (12.0, "number", "12"),
            (1234567, "integer", "1,234,567"),
            (1234.0, "integer", "1,234"),
            ("42", "integer", "42"),
            ("go", "text", "go"),
            (7, "text", "7"),
        ],
    )
    def test_numbers_and_text(self, value, formatter, text):
        assert format_cell({"f": value}, "f", formatter, {})["text"] == text

    @pytest.mark.spec("req-web-stdpanel-statcards-format-1")
    def test_a_non_number_is_shown_as_written_and_flagged(self):
        cell = format_cell({"f": "lots"}, "f", "integer", {})
        assert cell["text"] == "lots"
        assert cell["title"] == "not a number"
        assert format_cell({"f": True}, "f", "integer", {})["title"] == "not a number"

    @pytest.mark.spec("req-web-stdpanel-statcards-format-2")
    def test_datetime_carries_the_exact_utc_instant(self):
        cell = format_cell({"f": "2026-10-01T12:30:00+02:00"}, "f", "datetime", {})
        assert cell == {"kind": "time", "text": "2026-10-01T10:30:00Z", "iso": "2026-10-01T10:30:00Z"}

    @pytest.mark.spec("req-web-stdpanel-statcards-format-3")
    def test_age_carries_the_instant_for_the_browser_to_compute(self):
        cell = format_cell({"f": "2026-10-01T10:30:00Z"}, "f", "age", {})
        assert cell["kind"] == "age"
        assert cell["iso"] == "2026-10-01T10:30:00Z"

    @pytest.mark.spec("req-web-stdpanel-statcards-format-3")
    def test_an_unparseable_instant_is_shown_as_written(self):
        cell = format_cell({"f": "last tuesday"}, "f", "age", {})
        assert (cell["kind"], cell["text"], cell["title"]) == ("text", "last tuesday", "not a date-time")

    @pytest.mark.spec("req-web-stdpanel-statcards-format-4")
    def test_null_missing_and_blank_are_three_stated_states(self):
        row = {"nul": None, "blank": ""}
        assert format_cell(row, "nul", "integer", {}) == {"kind": "state", "state": "null", "text": "not observed"}
        assert format_cell(row, "gone", "integer", {})["state"] == "missing"
        assert format_cell(row, "blank", "text", {})["state"] == "blank"
        custom = {"null_text": "unscanned", "missing_text": "no such column", "blank_text": "empty"}
        assert [format_cell(row, f, "text", custom)["text"] for f in ("nul", "gone", "blank")] == [
            "unscanned",
            "no such column",
            "empty",
        ]

    @pytest.mark.spec("req-web-stdpanel-statcards-format-4")
    def test_zero_is_a_value_not_a_missing_one(self):
        assert format_cell({"n": 0}, "n", "integer", {}) == {"kind": "text", "text": "0"}


# ---------------------------------------------------------------------------
# req-web-stdpanel-statcards-card
# ---------------------------------------------------------------------------


class TestBuildCards:
    CONFIG = {
        "value_field": "n",
        "value_formatter": "integer",
        "title_field": "source",
        "title": "Fixed",
        "lines": [{"label": "Version", "field": "ver"}],
    }

    @pytest.mark.spec("req-web-stdpanel-statcards-card-1")
    def test_one_card_per_row_in_row_order(self):
        cards = build_cards([{"source": "a", "n": 1}, {"source": "b", "n": 2}], self.CONFIG)
        assert [(c["title"]["text"], c["value"]["text"]) for c in cards] == [("a", "1"), ("b", "2")]

    @pytest.mark.spec("req-web-stdpanel-statcards-card-2")
    def test_title_falls_back_to_the_fixed_title_when_the_row_has_none(self):
        cards = build_cards([{"source": None, "n": 1}, {"n": 2}], self.CONFIG)
        assert [c["title"]["text"] for c in cards] == ["Fixed", "Fixed"]
        assert build_cards([{"n": 1}], {"value_field": "n"})[0]["title"] is None

    @pytest.mark.spec("req-web-stdpanel-statcards-card-3")
    def test_lines_keep_config_order_and_state_a_missing_field(self):
        card = build_cards([{"n": 1}], {**self.CONFIG, "lines": [{"label": "Version", "field": "ver"}]})[0]
        assert card["lines"][0]["label"] == "Version"
        assert card["lines"][0]["cell"]["state"] == "missing"

    @pytest.mark.spec("req-web-stdpanel-statcards-card-4")
    def test_fixed_tone_and_neutral_default(self):
        assert build_cards([{"n": 1}], {"value_field": "n", "tone": "warn"})[0]["tone"] == "warn"
        assert build_cards([{"n": 1}], {"value_field": "n"})[0]["tone"] == "neutral"

    @pytest.mark.spec("req-web-stdpanel-statcards-card-4")
    def test_tone_is_chosen_by_a_field_value_through_the_map(self):
        cfg = {"value_field": "n", "tone": {"field": "n", "map": {"0": "good", "3": "bad"}, "default": "warn"}}
        cards = build_cards([{"n": 0}, {"n": 3}, {"n": 9}, {"n": None}], cfg)
        assert [c["tone"] for c in cards] == ["good", "bad", "warn", "warn"]
        no_default = {"value_field": "n", "tone": {"field": "n", "map": {"0": "good"}}}
        assert build_cards([{"n": 5}], no_default)[0]["tone"] == "neutral"

    @pytest.mark.spec("req-web-stdpanel-statcards-card-5")
    def test_a_tone_is_announced_in_words_and_the_words_are_configurable(self):
        cards = build_cards([{"n": 1}], {"value_field": "n", "tone": "bad"})
        assert cards[0]["tone_label"] == "Problem"
        custom = build_cards([{"n": 1}], {"value_field": "n", "tone": "bad", "tone_labels": {"bad": "Failing"}})
        assert custom[0]["tone_label"] == "Failing"
        assert build_cards([{"n": 1}], {"value_field": "n", "tone": "muted"})[0]["tone_label"] == ""


class TestZeroToneAndToneText:
    """`zero_tone` and `tone_text` (req-web-stdpanel-statcards-card-6, -card-7): panel config, not a per-card hardcode."""

    CONFIG = {"value_field": "n", "tone": "bad", "tone_text": True, "zero_tone": "muted"}

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    def test_a_zero_figure_takes_the_zero_tone_and_a_non_zero_keeps_its_tone(self):
        cards = build_cards([{"n": 0}, {"n": 3}], self.CONFIG)
        assert [(c["tone"], c["zero"]) for c in cards] == [("muted", True), ("bad", False)]

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    @pytest.mark.parametrize("zero", [0, 0.0, "0", "0.00", " 0 "])
    def test_every_spelling_of_the_number_zero_is_zero(self, zero):
        assert build_cards([{"n": zero}], self.CONFIG)[0]["tone"] == "muted"

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    @pytest.mark.parametrize("not_zero", [None, "", "none", False, 1, -1, "0.1"])
    def test_null_missing_text_and_booleans_are_not_zero(self, not_zero):
        assert build_cards([{"n": not_zero}], self.CONFIG)[0]["tone"] == "bad"
        assert build_cards([{"other": 1}], self.CONFIG)[0]["tone"] == "bad"

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    def test_zero_tone_overrides_a_tone_chosen_by_value_and_prints_no_word(self):
        cfg = {
            "value_field": "n",
            "tone": {"field": "n", "map": {"0": "good"}, "default": "warn"},
            "zero_tone": "muted",
        }
        card = build_cards([{"n": 0}], cfg)[0]
        assert card["tone"] == "muted" and card["tone_label"] == ""

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    def test_without_zero_tone_a_zero_keeps_its_tone(self):
        card = build_cards([{"n": 0}], {"value_field": "n", "tone": "bad"})[0]
        assert (card["tone"], card["zero"]) == ("bad", False)

    @pytest.mark.spec("req-web-stdpanel-statcards-card-7")
    def test_tone_text_is_a_flag_on_the_card(self):
        assert build_cards([{"n": 1}], self.CONFIG)[0]["tone_text"] is True
        assert build_cards([{"n": 1}], {"value_field": "n"})[0]["tone_text"] is False

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    @pytest.mark.spec("req-web-stdpanel-statcards-card-7")
    def test_the_config_validates_and_rejects_bad_values(self):
        _validate_config(self.CONFIG)
        for bad in ({"zero_tone": "red"}, {"tone_text": "yes"}, {"zero_tone": ""}):
            with pytest.raises(ValidationError):
                _validate_config({"value_field": "n", **bad})


class TestToneTextStyle:
    # No spec marker: req-web-stdpanel-statcards-style carries a `Trace: non-python` disposition (the stylesheet),
    # so it cannot also carry test evidence; style-4's proof is the computed colours read in a real browser.
    def test_the_tone_text_rules_use_the_edge_tokens_for_every_tone(self):
        from pathlib import Path

        css = (Path(__file__).resolve().parents[1] / "static/tap_web/css/stat-cards.css").read_text()
        assert "--statcard-ink: var(--statcard-accent)" in css  # the edge's own token drives the text
        assert ".tap-statcard--tone-text.tap-statcard--muted { --statcard-ink: var(--statcard-muted); }" in css
        for part in ("title", "value", "unit"):
            assert f".tap-statcard--tone-text .tap-statcard__{part}" in css


# ---------------------------------------------------------------------------
# req-web-stdpanel-statcards-render  (through the real panel endpoint)
# ---------------------------------------------------------------------------


# transaction=True: execute_search reads through the `search_readonly` connection, which sees only
# committed rows (the same marker the table panel's projection tests use).
@pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])
class TestRender:
    @pytest.mark.spec("req-web-stdpanel-statcards-render-1")
    def test_a_grouped_count_gives_one_card_per_group(self):
        _seed({"alpha": 2, "beta": 1})
        panel = _panel({"value_field": "n", "value_formatter": "integer", "title_field": "source", "unit": "open"})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert html.count('class="tap-statcard ') == 2
        by_title = dict(re.findall(r'tap-statcard__title">(\w+)</h3>\s*<p class="tap-statcard__value">(\d+)', html))
        assert by_title == {"alpha": "2", "beta": "1"}
        assert "tap-statcard__unit" in html

    @pytest.mark.spec("req-web-stdpanel-statcards-render-1")
    def test_an_all_aggregate_return_gives_a_single_card(self):
        _seed({"alpha": 2, "beta": 1})
        panel = _panel({"value_field": "n", "title": "Links"})
        _bind(panel, _COUNT_ALL)
        html = _get(panel)
        assert html.count('class="tap-statcard ') == 1
        assert re.search(r"tap-statcard__title\">Links</h3>\s*<p class=\"tap-statcard__value\">3", html)

    @pytest.mark.spec("req-web-stdpanel-statcards-render-2")
    def test_semantic_markup(self):
        _seed({"alpha": 1})
        panel = _panel({"value_field": "n", "title_field": "source", "lines": [{"label": "Seen", "field": "source"}]})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert '<ul class="tap-statcards" aria-label="Test Cards">' in html
        assert "<dl" in html and "<dt>Seen</dt>" in html and "<h3" in html

    @pytest.mark.spec("req-web-stdpanel-statcards-render-3")
    def test_tone_shows_as_text_as_well_as_a_class(self):
        _seed({"alpha": 2})
        panel = _panel({"value_field": "n", "tone": {"field": "n", "map": {"2": "bad"}}})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert "tap-statcard--bad" in html
        assert re.search(r'tap-statcard__tone"><span[^>]*></span>Problem</p>', html)

    @pytest.mark.spec("req-web-stdpanel-statcards-card-6")
    @pytest.mark.spec("req-web-stdpanel-statcards-card-7")
    def test_tone_text_and_a_grey_zero_reach_the_markup(self):
        _seed({"alpha": 2})
        nonzero = _panel({"value_field": "n", "tone": "bad", "tone_text": True, "zero_tone": "muted"})
        _bind(nonzero, _COUNT_ALL)
        html = _get(nonzero)
        assert 'class="tap-statcard tap-statcard--bad tap-statcard--tone-text"' in html
        assert "data-tap-zero" not in html
        zero = _panel({"value_field": "n", "tone": "bad", "tone_text": True, "zero_tone": "muted"})
        _bind(zero, ['MATCH (a:grid_fixtures__constrained_source) WHERE a.name = "nobody"', "RETURN COUNT(a) AS n"])
        html = _get(zero)
        assert 'class="tap-statcard tap-statcard--muted tap-statcard--tone-text"' in html
        assert 'data-tap-zero="true"' in html and "Problem" not in html
        plain = _panel({"value_field": "n", "tone": "bad"})
        _bind(plain, _COUNT_ALL)
        assert "tone-text" not in _get(plain)

    @pytest.mark.spec("req-web-stdpanel-statcards-render-4")
    def test_no_rows_shows_the_configured_empty_text(self):
        panel = _panel({"value_field": "n", "empty_text": "Nothing scanned yet."})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert "Nothing scanned yet." in html
        assert "tap-statcard " not in html

    @pytest.mark.spec("req-web-stdpanel-statcards-render-4")
    def test_a_field_the_search_does_not_return_is_stated_not_blank(self):
        _seed({"alpha": 1})
        panel = _panel({"value_field": "typo", "missing_text": "no such column"})
        _bind(panel, _COUNT_BY_SOURCE)
        assert 'data-tap-state="missing">no such column<' in _get(panel)

    @pytest.mark.spec("req-web-stdpanel-statcards-render-5")
    def test_a_node_returning_search_is_a_stated_error(self):
        _seed({"alpha": 1})
        panel = _panel({"value_field": "n"})
        _bind(panel, [_COUNT_ALL[0], "RETURN a"])
        assert "returned nodes, not rows" in _get(panel)

    @pytest.mark.spec("req-web-stdpanel-statcards-render-5")
    def test_no_search_and_bad_config_are_stated_errors(self):
        assert "No search linked" in _get(_panel({"value_field": "n"}))
        assert "Invalid stat-card config" in _get(_panel({"title": "no value field"}))

    @pytest.mark.spec("req-web-stdpanel-statcards-render-6")
    def test_max_cards_caps_and_says_so(self):
        _seed({"a": 1, "b": 1, "c": 1})
        panel = _panel({"value_field": "n", "title_field": "source", "max_cards": 2})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert html.count('class="tap-statcard ') == 2
        assert "1 more row not shown." in html

    @pytest.mark.spec("req-web-stdpanel-statcards-render-7")
    def test_values_are_escaped_and_no_inline_script_is_emitted(self):
        from tap_grid.models import Entity

        _seed({"alpha": 1})
        Entity.objects.filter(name="alpha").update(name="<script>alert(1)</script>")
        panel = _panel({"value_field": "n", "title_field": "source"})
        _bind(panel, _COUNT_BY_SOURCE)
        html = _get(panel)
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert not re.search(r"<script", html, re.I)

    @pytest.mark.spec("req-web-stdpanel-statcards-age-1")
    def test_a_datetime_and_an_age_cell_reach_the_browser_as_time_elements(self):
        from tap_web.panels.stat_card_panel import build_cards as _b

        cards = _b(
            [{"n": 1, "seen": "2026-10-01T10:30:00Z"}],
            {
                "value_field": "n",
                "lines": [
                    {"label": "Last report", "field": "seen", "formatter": "datetime"},
                    {"label": "Age", "field": "seen", "formatter": "age"},
                ],
            },
        )
        from django.template.loader import render_to_string

        html = render_to_string("tap_web/panels/_stat_card_cell.html", {"cell": cards[0]["lines"][0]["cell"]})
        assert '<time data-tap-localtime datetime="2026-10-01T10:30:00Z">' in html
        html = render_to_string("tap_web/panels/_stat_card_cell.html", {"cell": cards[0]["lines"][1]["cell"]})
        assert '<time data-tap-age datetime="2026-10-01T10:30:00Z" title="2026-10-01T10:30:00Z">' in html


@pytest.mark.django_db
class TestPageAssets:
    @pytest.mark.spec("req-web-stdpanel-statcards-type-2")
    def test_the_page_pipeline_collects_the_panels_assets(self):
        from tap_web.views import _get_panel_type_for_panel

        assert _get_panel_type_for_panel(_panel({"value_field": "n"})) is StatCardPanelType


@pytest.mark.spec("req-web-stdpanel-statcards-format-2")
def test_a_datetime_object_from_a_typed_field_is_an_instant_too():
    """A typed DateTimeField reaches the row as a datetime, not as text (seen on a real Gryphon row)."""
    from datetime import UTC, datetime

    cell = format_cell({"f": datetime(2026, 10, 1, 10, 30, tzinfo=UTC)}, "f", "age", {})
    assert cell == {"kind": "age", "text": "2026-10-01T10:30:00Z", "iso": "2026-10-01T10:30:00Z"}
    assert format_cell({"f": datetime(2026, 10, 1, 10, 30)}, "f", "datetime", {})["iso"] == "2026-10-01T10:30:00Z"
