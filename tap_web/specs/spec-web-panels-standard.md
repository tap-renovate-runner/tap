# Standard Panels Specification

## Philosophy

TAP Web needs a small set of built-in panel types that provide a baseline authoring experience without requiring plugin code for common cases. These standard panels live in `tap_web` and act as reference implementations for panel configuration, rendering, editor structure, and security expectations.

The first standard panel should be intentionally simple: a text panel that proves the full panel lifecycle end-to-end. That means a stored Panel object, a normal view template, an edit template, a small `config` object, standard preview/save behavior, and form-based editing with standard Django protections.

## Goals

|   |   |   |
| :---: | --- | --- |
| 1. | Baseline | Provide a small set of built-in panel types available without plugins |
| 2. | Reference | Establish a concrete example of panel view mode, edit mode, and config editing |
| 3. | Secure | Standard panel editors use Django's normal CSRF, validation, and escaping protections |
| 4. | Extensible | Standard panels should model the same panel object contract used by future custom panels |
| 5. | Minimal | The first panel type should be simple enough to validate the architecture without extra DSL work |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-web-stdpanel-base | [Standard Panel Types](#standard-panel-types) | Implemented | `tap_web/panels/` package; `TextPanelType` registered in `panel_type_registry` |
| req-web-stdpanel-text | [Text Panel](#text-panel) | Implemented | Renders title + `config.text`; description is admin metadata |
| req-web-stdpanel-text-edit | [Text Panel Editor](#text-panel-editor) | Implemented | `TextPanelEditForm`; Django Form validation; typed editor replaces generic JSON editor |
| req-web-stdpanel-statcards | [Stat Cards Panel](#stat-cards-panel) | Implemented | One metric card per row of the bound Search's `rows` result; `StatCardPanelType`, slug `stat-cards` |
| req-web-stdpanel-statcards-type | [Stat Cards Panel Type](#stat-cards-panel-type) | Implemented | Registration, assets, defaults; `tap_web/panels/stat_card_panel/` |
| req-web-stdpanel-statcards-config | [Stat Cards Config](#stat-cards-config) | Implemented | `STAT_CARD_CONFIG_SCHEMA`: fields named by row alias, never values; every entry described |
| req-web-stdpanel-statcards-format | [Stat Cards Formatters](#stat-cards-formatters) | Implemented | `text`, `number`, `integer`, `datetime`, `age`; null / missing / blank are three stated states |
| req-web-stdpanel-statcards-card | [Stat Card Anatomy](#stat-card-anatomy) | Implemented | Title, figure, unit, secondary lines, tone chosen fixed or by a field's value |
| req-web-stdpanel-statcards-render | [Stat Cards Rendering](#stat-cards-rendering) | Implemented | Semantic server-rendered markup; empty state; stated errors; card cap |
| req-web-stdpanel-statcards-age | [Stat Cards Age And Local Time](#stat-cards-age-and-local-time) | Implemented | Age computed in the browser against now; exact timestamp in the tooltip |
| req-web-stdpanel-statcards-style | [Stat Cards Styling](#stat-cards-styling) | Implemented | Responsive wrapping grid; light and dark tokens; tone never by colour alone |

### Standard Panel Types
----
RID: `req-web-stdpanel-base`

Status: `Implemented`

Standard panel types are the built-in panel implementations that ship with `tap_web`. They provide core reusable panel behavior without relying on plugins.

#### Status Details
`tap_web/panels/` is the home for built-in panel type packages. `TextPanelType` is the first entry, registered with `panel_type_registry` in `TapWebConfig.ready()`.

#### Implementation
- Standard panel types live inside `tap_web/panels/`, one subpackage per type.
- Each panel type is a plain class (descriptor) with: `slug`, `label`, `view`, `editor_view`, `config_defaults`, and optionally `form_class`.
- Panel types are registered with `panel_type_registry` (a `ScopedRegistry[type]` in `tap_web/registry.py`) at app startup.
- Standard panels use the same `Panel` object contract defined in `spec-web-panel.md`:
  - `view`
  - optional `editor_view`
  - `config`
  - `js` / `css`
  - `editor_js` / `editor_css`
- Standard panels are intended to be readable reference implementations for future panel types.

#### Development
Keep built-in panel types small and obvious. They should prove the architecture, not compete with richer plugin panels.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-base-1 | Built-in Panels Live In tap_web | Implemented | Standard panel type implementations live in `tap_web/panels/` rather than a plugin package. | `tap_web/panels/text_panel/` |
| req-web-stdpanel-base-2 | Standard Panels Use Core Panel Contract | Implemented | Standard panels conform to the generic Panel object contract defined in `spec-web-panel.md`. | `TextPanelType` uses `view`, `editor_view`, `config`. |
| req-web-stdpanel-base-3 | Standard Panels Are Reference Implementations | Implemented | Standard panels are intended to serve as readable examples of panel rendering and editing patterns. | `TextPanelType` + `TextPanelEditForm` in `tap_web/panels/text_panel/`. |

#### Future
Add additional built-in panel types as separate standards once the text panel pattern is proven.

The Table Panel has been split into its own draft standard at `tap_web/specs/spec-web-panels-standard-table.md` so search binding, mixed-result handling, and pagination can evolve without overloading this catalog spec.

### Text Panel
----
RID: `req-web-stdpanel-text`

Status: `Implemented`

The Text Panel is the simplest standard built-in panel type. It renders a name and body text using the generic Panel object plus a small `config` payload. `description` remains backend/admin metadata rather than rendered body content.

#### Status Details
Implemented as `TextPanelType` in `tap_web/panels/text_panel/`. View template at `tap_web/panels/text_panel.html`.

#### Implementation
Text Panel data is stored as:
- `Panel.name` (canonical entity instance name)
- `Panel.description`
- `Panel.config.text`

Text Panel behavior:
- normal panel rendering displays `Panel.name` and `config.text`
- `description` is backend/admin metadata and is not part of the rendered panel body
- body text is plain text content, not trusted HTML
- Text Panel uses a normal `view` template and may omit panel-specific JS/CSS in the first implementation

The Text Panel does not require page inputs in its initial form.

#### Development
Keep the first text panel intentionally boring. The value is in proving panel object storage, normal rendering, and editor flow end-to-end.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-text-1 | Text Stored In Core Fields Plus Config | Implemented | Text Panel uses `Panel.name`, `description`, and `config.text` as its stored content model. | `description` is metadata, not rendered body content. |
| req-web-stdpanel-text-2 | Rendered Content Is Name Plus Text | Implemented | Text Panel renders `Panel.name` plus `config.text`, with body text treated as plain text rather than trusted HTML. | `tap_web/panels/text_panel.html`; auto-escaping enforced. |
| req-web-stdpanel-text-3 | No Inputs Required | Implemented | The initial Text Panel does not require `input_vars`. | `config_defaults = {"text": ""}` only. |

#### Future
Consider richer text variants later, but keep the first version plain text only.

### Text Panel Editor
----
RID: `req-web-stdpanel-text-edit`

Status: `Implemented`

The Text Panel editor is a simple HTML form that edits the panel's title, description, and body text.

#### Status Details
Implemented as `TextPanelEditForm` (Django Form) in `tap_web/panels/text_panel/`. Editor template at `tap_web/panels/text_panel_editor.html`. The `panel_edit_view` dispatches to the typed form when a `PanelType` with `form_class` is registered for the panel's `view` path.

#### Implementation
The Text Panel editor:
- uses the generic web editor shell defined in `spec-web-editor.md` and the panel edit route integration defined in `spec-web-rendering.md`
- renders a simple HTML form in `editor_view` (`tap_web/panels/text_panel_editor.html`), included inside the outer `panel_edit.html` form when a typed form is present
- edits:
  - `name`
  - `description`
  - `config.text`
- panel preview behavior follows the shared generic editor preview contract
- save is the explicit POST action

Security behavior for standard panel editors is defined in `spec-web-panel-security.md`.

#### Development
The first editor looks like normal Django form handling. `TextPanelEditForm` is a reference for future panel editors.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-text-edit-1 | Simple Form Editor | Implemented | Text Panel editor uses a simple HTML form (`TextPanelEditForm`) rather than a rich editor UI. | |
| req-web-stdpanel-text-edit-2 | Editable Fields | Implemented | Text Panel editor edits `name` (entity name), `description`, and `config.text`. | |
| req-web-stdpanel-text-edit-3 | Preview And Save | Proposed | Text Panel editor participates in the shared preview-without-save and explicit save contract. | Cross-ref `req-web-editor-preview-exec`. |
| req-web-stdpanel-text-edit-4 | Security Delegated | Implemented | Text Panel editor security behavior is governed by `spec-web-panel-security.md` (CSRF, server-side sanitization, auto-escaping). | `req-web-panel-edit-form.sec` + `req-web-panel-render-content.sec` both Implemented. |
| req-web-stdpanel-text-edit-5 | Editable Fields Persist Safely | Implemented | Text Panel editor persists `name`, `description`, and `config.text` through `form.cleaned_data` via the standard panel edit flow. | |
| req-web-stdpanel-text-edit-6 | Plain Text Saved Content | Implemented | Submitted text is stored and later rendered as plain text via Django auto-escaping. | Verified in `test_text_panel.py`. |

#### Future
If common editor patterns emerge across built-in panels, implement them through the generic editor shell and typed editor descriptor contract rather than duplicating form structure in every panel type.

### Stat Cards Panel
----
RID: `req-web-stdpanel-statcards`

Status: `Implemented`

Trace: `process` — umbrella requirement; its behaviour is demonstrated by the sub-requirements below, each of which carries its own trace

The Stat Cards Panel shows a row of metric cards ("Open vulnerabilities 20", "Highest CVSS 9.8", "Oldest open 19 days"), one card per row of the `rows` result of ONE bound Search. It exists beside the Text Panel (fixed text, no values from a Search) and the Table Panel (many rows, many columns): it is the panel for a few headline figures, or for a small group-by that should read as a row of tiles rather than a table.

#### Status Details
Implemented as `StatCardPanelType` in `tap_web/panels/stat_card_panel/`, registered under the slug `stat-cards` in `TapWebConfig.ready()`. It is a data-only panel for projects: a project plugin ships a Search, a Panel node whose `config` is the JSON below, and a `USES_SEARCH` edge, and writes no code (nothing in the panel names a value, node id or tool).

#### Implementation
- The panel binds to a Search exactly as the Table Panel does: the earliest `USES_SEARCH` edge from the panel (`tap_web.panel.get_panel_search`), executed through `tap_grid.search.execute_search`, page inputs coerced by the Search's own `input_schema` (`inputs_from_query`).
- It reads the envelope's `rows` (`req-grid-gryphon-rows`): one row per GROUP BY key combination, or a single row when the RETURN is all aggregates (`req-grid-gryphon-count`). Rows are not paged by `execute_search`, so the panel caps its own output (`max_cards`).
- A Search that RETURNs nodes yields no rows; the panel says so rather than drawing nothing (`req-web-stdpanel-statcards-render-5`).

#### Development
Keep the panel declarative. A new kind of figure is a new formatter name in the closed vocabulary, never a branch on a field name.

#### Future
A card that links somewhere (`href_template`, as the Table Panel's `row_url_template`); a sparkline under the figure; an in-page typed editor (`editor_view` is empty today, so the generic panel editor edits `config` as JSON); viewer-locale digit grouping for `number` / `integer` (today a fixed `1,234` grouping, rendered on the server); `MIN` / `MAX` aggregates feed the "highest" and "oldest" cards once `req-grid-gryphon-minmax` lands.

### Stat Cards Panel Type
----
RID: `req-web-stdpanel-statcards-type`

Status: `Implemented`

The panel type descriptor and its registration.

#### Implementation
`StatCardPanelType`: `slug = "stat-cards"`, `label = "Stat Cards"`, `view = "tap_web/panels/stat_card_panel.html"`, `editor_view = ""`, `css = ["tap_web/css/stat-cards.css"]`, `js = ["tap_web/js/stat-cards.js"]`, `config_defaults = {"max_cards": 24}`. The page pipeline collects `css` / `js` from the panel type (`_get_panel_type_for_panel`), so a page that mounts the panel loads them.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-type-1 | Registered | Implemented | The panel type is registered in `panel_type_registry` under the slug `stat-cards`. | `TapWebConfig.ready()` |
| req-web-stdpanel-statcards-type-2 | Assets Declared And Shipped | Implemented | The type declares one stylesheet and one script, both present in `tap_web/static`, and the page pipeline collects them from the type rather than from the instance. | |
| req-web-stdpanel-statcards-type-3 | Defaults | Implemented | `config_defaults` supplies `max_cards` only; the one required key, `value_field`, has no default because a default would be a hardcoded field name. | |

### Stat Cards Config
----
RID: `req-web-stdpanel-statcards-config`

Status: `Implemented`

Panel `config` declares the cards by FIELD NAME of the returned row, never by value. It validates against `STAT_CARD_CONFIG_SCHEMA` (`additionalProperties: false`) on every render; an invalid config renders a stated error, never a half-drawn card.

#### Implementation
All keys except `value_field` are optional.

| Key | Type | Meaning |
| --- | --- | --- |
| `value_field` | string, required | Row alias of the main figure. |
| `value_formatter` | `text` \| `number` \| `integer` \| `datetime` \| `age` | Formatter of the figure; `text` when omitted. |
| `unit` | string | Fixed unit or label beside the figure (hidden when the figure is a stated state). |
| `title_field` | string | Row alias shown as the card title. |
| `title` | string | Fixed title, used when `title_field` is absent or the row has no value for it. |
| `lines` | array of `{label, field, formatter?}` | Secondary label/value lines, in order. |
| `tone` | tone name, or `{field, map, default?}` | Fixed tone, or the tone chosen by the row value of `field` through `map` (value as text to tone), `default` (else `neutral`) for an unlisted value. Tones: `neutral`, `good`, `warn`, `bad`, `muted` (the Table Panel's `toneBadge` vocabulary, plus `neutral`). |
| `tone_labels` | object, tone name to string | Replaces the words that announce a tone; `""` shows none. |
| `empty_text` | string | Shown when the Search returns no rows. Default `No results.` |
| `null_text` | string | Shown for a null (unobserved) value. Default `not observed`. |
| `missing_text` | string | Shown when the row has no such field. Default `not returned by the search`. |
| `blank_text` | string | Shown for an empty string (observed, empty). Default `(empty)`. |
| `max_cards` | integer 1..200 | Cap on cards drawn. Default 24. |
| `hide_header` | boolean | Omit the panel name heading. |

Example, one fleet card (a Search `RETURN COUNT(v) AS open`):

```json
{
  "title": "Open vulnerabilities",
  "value_field": "open",
  "value_formatter": "integer",
  "tone": {"field": "open", "map": {"0": "good"}, "default": "warn"},
  "hide_header": true
}
```

Example, one card per scanner (a Search `RETURN s.name AS scanner, s.host AS runs_at, s.version AS version, s.last_report AS last_report, COUNT(v) AS open`):

```json
{
  "title_field": "scanner",
  "value_field": "open",
  "value_formatter": "integer",
  "unit": "open",
  "lines": [
    {"label": "Runs at", "field": "runs_at"},
    {"label": "Last report", "field": "last_report", "formatter": "datetime"},
    {"label": "Reported", "field": "last_report", "formatter": "age"},
    {"label": "Version", "field": "version"}
  ],
  "null_text": "not observed",
  "empty_text": "No scanners have reported."
}
```

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-config-1 | Strict Schema | Implemented | `value_field` is required and any undeclared key is rejected. | |
| req-web-stdpanel-statcards-config-2 | Closed Vocabulary | Implemented | Formatters are the five named; tones are the five named; `lines`, `tone` and `max_cards` are bounded and malformed values are rejected. | |
| req-web-stdpanel-statcards-config-3 | Self-Describing | Implemented | The schema and every entry of it, including `lines[]` items and the `tone` object, carry a `description`. | Repo rule: JSON structures require descriptions. |
| req-web-stdpanel-statcards-config-4 | No Domain Values | Implemented | Nothing in the schema enumerates a domain value, node id or tool name; the only enums are the formatter and tone vocabularies. | |

### Stat Cards Formatters
----
RID: `req-web-stdpanel-statcards-format`

Status: `Implemented`

A formatter turns one row value into a cell. Every cell is either a value or one of three STATED states; none is ever blank.

#### Implementation
- `text`: the value as written. `number`: a plain number, thousands separator, trailing zeros dropped (`9.8`, `1,234.5`). `integer`: rounded, thousands separator (`1,234`). A value that is not a number is shown as written with the tooltip `not a number`.
- `datetime`: a `<time data-tap-localtime datetime="…Z">` that `localtime.js` shows in the viewer's locale and zone with the exact UTC instant in the tooltip (`req-web-time-single-helper`: the same helper the Table Panel's `datetime` column uses; no code is copied).
- `age`: see `req-web-stdpanel-statcards-age`.
- A field the row does not carry is `missing` (a Search/config mismatch, `missing_text`); a null is `null` (unobserved, `null_text`); an empty string is `blank` (observed-empty, `blank_text`) — the grid's convention that null means unobserved and `""` means observed-empty. Zero is a value.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-format-1 | Number Formatters | Implemented | `number` and `integer` format with a thousands separator; text is untouched; a non-number is shown as written and flagged. | |
| req-web-stdpanel-statcards-format-2 | Date-Time | Implemented | `datetime` normalizes to the exact UTC instant and renders a `<time data-tap-localtime>` for the shared local-time helper. | |
| req-web-stdpanel-statcards-format-3 | Age Carries The Instant | Implemented | `age` renders the exact UTC instant for the browser to measure; an unparseable value is shown as written. | |
| req-web-stdpanel-statcards-format-4 | Three Stated States | Implemented | Missing, null and empty-string values each render configured text in a distinct style, never an empty cell; zero is a value. | |

### Stat Card Anatomy
----
RID: `req-web-stdpanel-statcards-card`

Status: `Implemented`

#### Implementation
One card per row, in row order: an optional title (`title_field` value, else the fixed `title`), the main figure with its optional unit, an optional tone word, and the `lines` as a definition list. Tone is the fixed `tone`, or the one the row's own value picks through the `map` (so a count of zero can read `good` and a count above zero `warn`, declared in data).

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-card-1 | One Card Per Row | Implemented | Each row of the Search's `rows` result becomes one card, in row order. | |
| req-web-stdpanel-statcards-card-2 | Title | Implemented | The title is the `title_field` value; when the row has none, the fixed `title`; with neither, the card has no title. | |
| req-web-stdpanel-statcards-card-3 | Secondary Lines | Implemented | `lines` render in declared order, each with its own formatter, and each state a missing or null field. | |
| req-web-stdpanel-statcards-card-4 | Tone | Implemented | Tone is fixed, or chosen by a field's value through a map with a default; no tone is `neutral`. | |
| req-web-stdpanel-statcards-card-5 | Tone In Words | Implemented | A `good` / `warn` / `bad` card also prints a word for its tone (`Good`, `Warning`, `Problem`, overridable by `tone_labels`); `neutral` and `muted` print none. | Colour is never the only signal. |

### Stat Cards Rendering
----
RID: `req-web-stdpanel-statcards-render`

Status: `Implemented`

#### Implementation
Server-rendered, with no inline script. Template `tap_web/panels/stat_card_panel.html`: a `<ul class="tap-statcards" aria-label="<panel name>">` of `<li class="tap-statcard tap-statcard--<tone>">`; the title is an `<h3>`, the figure a `<p>`, secondary lines a `<dl>`. The panel name heading is the shared panel header unless `hide_header`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-render-1 | Rows Become Cards | Implemented | A grouped `COUNT … AS n` search gives one card per group; an all-aggregate RETURN gives a single card. | Real Gryphon search over seeded grid rows. |
| req-web-stdpanel-statcards-render-2 | Semantic Markup | Implemented | The cards are a labelled list, titles are headings and secondary lines a definition list. | |
| req-web-stdpanel-statcards-render-3 | Tone As Text | Implemented | A toned card carries its tone class and its tone word in the markup. | |
| req-web-stdpanel-statcards-render-4 | Empty And Missing Are Stated | Implemented | No rows shows `empty_text`; a field the search does not return shows `missing_text`. | |
| req-web-stdpanel-statcards-render-5 | Errors Are Stated | Implemented | No linked search, an invalid config, a failed search, or a search that returns nodes instead of rows each render an alert with the reason. | |
| req-web-stdpanel-statcards-render-6 | Card Cap | Implemented | More rows than `max_cards` draw `max_cards` cards and a notice counting the rest. | |
| req-web-stdpanel-statcards-render-7 | Escaped | Implemented | Row values are auto-escaped and the fragment emits no inline script. | `req-web-panel-render-content.sec` |

### Stat Cards Age And Local Time
----
RID: `req-web-stdpanel-statcards-age`

Status: `Implemented`

The `age` formatter shows how long ago an instant was ("19 days", "3 hours"), computed in the browser against the viewer's now, with the exact timestamp in the tooltip.

#### Implementation
The server emits `<time data-tap-age datetime="<UTC ISO>" title="<UTC ISO>"><UTC ISO></time>`, which is the whole no-JavaScript rendering. `tap_web/static/tap_web/js/stat-cards.js` replaces the text with `formatAge` (under a minute; N minutes; N hours; N days up to 60; N months; N years; a future instant reads "in …") and the tooltip with the shared `TapLocalTime` title (`YYYY-MM-DD HH:MM:SS UTC`). It re-runs after every HTMX settle and once a minute. It names no field, panel or tool.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-age-1 | Time Element Contract | Implemented | `datetime` and `age` cells reach the browser as `<time>` elements carrying the exact UTC instant. | |
| req-web-stdpanel-statcards-age-2 | Browser Computes Age | Implemented | The visible age is computed in the browser from the instant and now, in singular/plural units. | Proven in a real browser; no JS test runner exists in the repo. |
| req-web-stdpanel-statcards-age-3 | Exact Timestamp In Tooltip | Implemented | The tooltip is the exact UTC timestamp. | |
| req-web-stdpanel-statcards-age-4 | Stays Fresh | Implemented | Ages recompute after an HTMX swap and every minute. | |

### Stat Cards Styling
----
RID: `req-web-stdpanel-statcards-style`

Status: `Implemented`

Trace: `non-python` — tap_web/static/tap_web/css/stat-cards.css

#### Implementation
`tap_web/static/tap_web/css/stat-cards.css`: the cards lay out as `grid-template-columns: repeat(auto-fill, minmax(min(11rem, 100%), 1fr))`, so a panel wraps its cards to whatever width its page slot gives and a row of several panels each wraps independently, down to one column at phone width. Colours are custom properties on the panel root with dark values under `prefers-color-scheme: dark` and `[data-theme="dark"]` (guarded by `[data-theme="light"]`). Tone is a left rule plus the tone word.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-web-stdpanel-statcards-style-1 | Responsive Wrapping Grid | Implemented | Cards wrap in an auto-fill grid and never overflow the panel at phone width. | |
| req-web-stdpanel-statcards-style-2 | Light And Dark Tokens | Implemented | Colours are tokens with light and dark values. | |
| req-web-stdpanel-statcards-style-3 | Null Styled Apart | Implemented | A stated state (null, missing, blank) is italic and muted so it cannot pass for a value. | |

## Status Vocabulary

| Status States |  |
| --- | --- |
| Proposed |  |
| Approved for Development | Requirement is accepted and ready to be implemented |
| In Development |  |
| Implemented |  |
| Verified |  |
| Refactoring |  |
| Deprecating |  |
| Deprecated | Not part of the current architecture and should not be implemented |

## RID Format

`req-<application>-<specification>-<feature>-<sub-feature>`

## Requirements Format

`RID: `...``
`Status: `...``

| Sub-Sections | (as needed) |
| --- | --- |
| Status Details |  |
| Implementation |  |
| Development |  |
| Acceptance Criteria |  |
| Future |  |
