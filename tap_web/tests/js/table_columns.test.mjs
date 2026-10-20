// Table panel column options: field_path (req-web-stdpanel-table-config-22) and empty_text (-23).
// Run with `node --test`; tap_web/tests/test_table_panel.py::test_js_columns runs it when node exists.
// panel-table.js is a browser IIFE: it is loaded into a vm context with stub globals and the test seam
// (window.__TAP_TABLE_TEST__) hands back the pure column builders. No Tabulator or DOM is needed.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const src = readFileSync(new URL("../../static/tap_web/js/panel-table.js", import.meta.url), "utf8");
const seam = {};
const window = {__TAP_TABLE_TEST__: seam, location: {href: "http://x/", origin: "http://x", pathname: "/"}};
const document = {readyState: "complete", addEventListener() {}, querySelectorAll: () => [], documentElement: {}};
vm.runInNewContext(src, {window, document, history: {}, sessionStorage: {}, console, URL});
const {buildCustomColumns, resolveFieldPaths} = seam;

const cellOf = (value) => ({getValue: () => value});
const render = (spec, value) => buildCustomColumns([spec])[0].formatter(cellOf(value), {}, () => {});

test("the seam exposes the builders", () => {
    assert.equal(typeof buildCustomColumns, "function");
    assert.equal(typeof resolveFieldPaths, "function");
});

test("field_path reaches a key that itself contains a dot", () => {
    const rows = [
        {dimensions: {"dataclass.customer": "high", dataclass: {customer: "WRONG"}}},
        {dimensions: {}},
        {dimensions: null},
        {},
    ];
    const specs = resolveFieldPaths([{field_path: ["dimensions", "dataclass.customer"], title: "T"}], rows);
    const key = specs[0].field;
    assert.ok(key && !key.includes("."), "the synthetic key is dot-free so Tabulator reads it flat");
    assert.deepEqual(rows.map((r) => r[key]), ["high", undefined, undefined, undefined]);
    assert.equal(buildCustomColumns(specs)[0].field, key);
});

test("field_path columns in a group get distinct keys, and plain field columns are untouched", () => {
    const rows = [{a: {"b.c": 1, d: 2}, plain: 3}];
    const specs = resolveFieldPaths(
        [{field: "plain", title: "P"}, {title: "G", columns: [{field_path: ["a", "b.c"], title: "X"}, {field_path: ["a", "d"], title: "Y"}]}],
        rows,
    );
    assert.equal(specs[0].field, "plain");
    const [x, y] = specs[1].columns;
    assert.notEqual(x.field, y.field);
    assert.deepEqual([rows[0][x.field], rows[0][y.field]], [1, 2]);
});

test("a dotted field still resolves as before (no field_path means no change)", () => {
    const specs = [{field: "dimensions.dataclass.customer", title: "T"}];
    assert.deepEqual(resolveFieldPaths(specs, [{}]), specs);
});

test("empty_text replaces a null, missing or empty value for the default formatter, escaped", () => {
    const spec = {field: "f", title: "T", empty_text: "<n/a> & co"};
    for (const v of [null, undefined, ""]) assert.equal(render(spec, v), "&lt;n/a&gt; &amp; co");
    assert.equal(render(spec, "<b>x</b>"), "&lt;b&gt;x&lt;/b&gt;", "a real value is still escaped plain text");
    assert.equal(render(spec, 0), "0", "zero is a value");
    assert.equal(render(spec, false), "false", "false is a value");
});

test("empty_text applies with every declared formatter, never leaving a blank", () => {
    const names = ["toneBadge", "toneThreshold", "percent", "link", "externalLink", "datetime", "capitalized", "json", "tickCross", "arrayCount", "linkList", "ciaLevel", "ellipsisSuffix"];
    for (const formatter of names) {
        for (const v of [null, undefined, ""]) {
            assert.equal(render({field: "f", title: "T", formatter, empty_text: "none yet"}, v), "none yet", `${formatter} ${v}`);
        }
    }
});

test("without empty_text the column is exactly as before", () => {
    const col = buildCustomColumns([{field: "f", title: "T"}])[0];
    assert.equal(col.formatter(cellOf(null)), "");
    const tone = buildCustomColumns([{field: "f", title: "T", formatter: "percent"}])[0];
    assert.notEqual(tone.formatter(cellOf(0.5), {}, () => {}), "none yet");
});

test("empty_text and a non-empty value hand over to the column formatter", () => {
    const out = render({field: "f", title: "T", formatter: "percent", empty_text: "n/a"}, 0.25);
    assert.match(out, /25/);
    assert.doesNotMatch(out, /n\/a/);
});
