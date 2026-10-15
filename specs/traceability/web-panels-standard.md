<!-- GENERATED TRACEABILITY FRAGMENT — manage.py guards --sync-accounting / --sync-evidence; do not hand-edit -->

# `tap_web/specs/spec-web-panels-standard.md`

| Bucket | Count |
| --- | ---: |
| mapped | 6 |
| excluded | 2 |
| unaccounted | 3 |
| 0-ACID (payable) | 0 |

## Exclusions

Reasons verbatim from each `Trace:` line; ⚠ marks zero-ACID exempt.

| RID | Category | 0-ACID | Reason |
| --- | --- | :---: | --- |
| `req-web-stdpanel-statcards` | process | ⚠ | umbrella requirement; its behaviour is demonstrated by the sub-requirements below, each of which carries its own trace |
| `req-web-stdpanel-statcards-style` | non-python |  | tap_web/static/tap_web/css/stat-cards.css |

## Evidence

| Requirement | Declared | Derived | Implementation | Verified by |
| --- | --- | --- | --- | --- |
| `req-web-stdpanel-statcards-age` | Implemented | Tested | — | `req-web-stdpanel-statcards-age-1` |
| `req-web-stdpanel-statcards-card` | Implemented | Tested | — | `req-web-stdpanel-statcards-card-1`, `req-web-stdpanel-statcards-card-2`, `req-web-stdpanel-statcards-card-3`, `req-web-stdpanel-statcards-card-4`, `req-web-stdpanel-statcards-card-5` |
| `req-web-stdpanel-statcards-config` | Implemented | Tested | — | `req-web-stdpanel-statcards-config-1`, `req-web-stdpanel-statcards-config-2`, `req-web-stdpanel-statcards-config-3`, `req-web-stdpanel-statcards-config-4` |
| `req-web-stdpanel-statcards-format` | Implemented | Tested | — | `req-web-stdpanel-statcards-format-1`, `req-web-stdpanel-statcards-format-2`, `req-web-stdpanel-statcards-format-3`, `req-web-stdpanel-statcards-format-4` |
| `req-web-stdpanel-statcards-render` | Implemented | Tested | — | `req-web-stdpanel-statcards-render-1`, `req-web-stdpanel-statcards-render-2`, `req-web-stdpanel-statcards-render-3`, `req-web-stdpanel-statcards-render-4`, `req-web-stdpanel-statcards-render-5`, `req-web-stdpanel-statcards-render-6`, `req-web-stdpanel-statcards-render-7` |
| `req-web-stdpanel-statcards-type` | Implemented | Tested | — | `req-web-stdpanel-statcards-type-1`, `req-web-stdpanel-statcards-type-2`, `req-web-stdpanel-statcards-type-3` |
