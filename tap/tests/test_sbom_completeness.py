"""SBOM field-completeness check (req-cicd-sbom-32) - pure-function and CLI tests.

The fixture `fixtures/sbom/tap-web-trimmed.cdx.json` is 14 components cut with `jq` from the attested tap-web
arm64 CycloneDX 1.7 document (Syft 1.51.0): the operating-system entry, three apk packages with an `upstream=`
qualifier, three without, two pypi, two npm (one library twice), the generic FIPS provider and the github-type
uv/uvx entries. Every seeded defect below deletes ONE field from a deep copy of it, so a pass is not vacuous
(req-cicd-sbom-32-9).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sbom_completeness", _REPO_ROOT / "scripts" / "sbom" / "completeness.py")
assert _spec is not None and _spec.loader is not None
comp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(comp)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sbom" / "tap-web-trimmed.cdx.json"


@pytest.fixture(name="doc")
def _doc() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(name="rules")
def _rules() -> dict[str, Any]:
    loaded: dict[str, Any] = comp.load_rules()
    return loaded


def _first(doc: dict[str, Any], prefix: str, *, with_upstream: bool | None = None) -> dict[str, Any]:
    for component in doc["components"]:
        purl = component.get("purl") or ""
        if not purl.startswith(prefix):
            continue
        if with_upstream is not None and ("upstream=" in purl) != with_upstream:
            continue
        found: dict[str, Any] = component
        return found
    raise AssertionError(f"no component with prefix {prefix}")


def _drop_qualifier(component: dict[str, Any], key: str) -> None:
    base, _, query = component["purl"].partition("?")
    kept = [pair for pair in query.split("&") if not pair.startswith(f"{key}=")]
    component["purl"] = base + ("?" + "&".join(kept) if kept else "")


def _property(doc: dict[str, Any], name: str) -> str | None:
    for prop in doc["metadata"].get("properties", []):
        if prop["name"] == name:
            return str(prop["value"])
    return None


@pytest.mark.spec("req-cicd-sbom-32-9")
def test_the_real_shape_document_is_complete(doc, rules):
    result = comp.check_completeness(doc, rules)
    assert result["verdict"] == "complete", result["counts"]
    assert result["components"] == 14


DEFECTS: dict[str, Callable[[dict[str, Any]], object]] = {
    "purl": lambda d: _first(d, "pkg:pypi").pop("purl"),
    "purl-qualifier:arch": lambda d: _drop_qualifier(_first(d, "pkg:apk"), "arch"),
    "purl-qualifier:distro": lambda d: _drop_qualifier(_first(d, "pkg:apk"), "distro"),
    "purl-qualifier:upstream": lambda d: _drop_qualifier(_first(d, "pkg:apk", with_upstream=True), "upstream"),
    "cpe": lambda d: _first(d, "pkg:pypi").pop("cpe"),
    "origin-package": lambda d: _first(d, "pkg:apk").__setitem__(
        "properties", [p for p in _first(d, "pkg:apk")["properties"] if p["name"] != "syft:metadata:originPackage"]
    ),
}


@pytest.mark.spec("req-cicd-sbom-32-3")
@pytest.mark.spec("req-cicd-sbom-32-9")
@pytest.mark.parametrize("gap_class", sorted(DEFECTS))
def test_each_deleted_field_is_thin_and_names_its_class(gap_class, doc, rules):
    broken = copy.deepcopy(doc)
    DEFECTS[gap_class](broken)
    result = comp.check_completeness(broken, rules)
    if gap_class == "purl":
        # A component with no purl is not in a ruled ecosystem: it surfaces as unruled (req-cicd-sbom-32-11).
        assert result["verdict"] == "thin"
        assert "unruled-ecosystem" in result["counts"]
        return
    assert result["verdict"] == "thin"
    assert list(result["counts"]) == [gap_class]
    assert result["counts"][gap_class] == 1


@pytest.mark.spec("req-cicd-sbom-32-4")
def test_upstream_is_required_only_when_the_origin_differs(doc, rules):
    same = _first(doc, "pkg:apk", with_upstream=False)
    origin = next(p["value"] for p in same["properties"] if p["name"] == "syft:metadata:originPackage")
    assert origin == same["name"]  # the fixture's no-upstream packages are exactly the origin == name ones
    assert comp.check_completeness(doc, rules)["verdict"] == "complete"
    differing = _first(doc, "pkg:apk", with_upstream=True)
    origin = next(p["value"] for p in differing["properties"] if p["name"] == "syft:metadata:originPackage")
    assert origin != differing["name"]
    # An origin that differs without the qualifier is a gap; the same package with equal origin is not.
    broken = copy.deepcopy(doc)
    _drop_qualifier(_first(broken, "pkg:apk", with_upstream=True), "upstream")
    assert comp.check_completeness(broken, rules)["counts"] == {"purl-qualifier:upstream": 1}


@pytest.mark.spec("req-cicd-sbom-32-5")
def test_exactly_one_operating_system_component_with_name_and_version(doc, rules):
    none = copy.deepcopy(doc)
    none["components"] = [c for c in none["components"] if c["type"] != "operating-system"]
    assert comp.check_completeness(none, rules)["counts"] == {"os-component": 1}
    two = copy.deepcopy(doc)
    two["components"].append(copy.deepcopy(next(c for c in two["components"] if c["type"] == "operating-system")))
    assert comp.check_completeness(two, rules)["counts"] == {"os-component": 1}
    no_version = copy.deepcopy(doc)
    next(c for c in no_version["components"] if c["type"] == "operating-system").pop("version")
    assert comp.check_completeness(no_version, rules)["counts"] == {"os-component": 1}


@pytest.mark.spec("req-cicd-sbom-32-11")
def test_a_component_without_a_rule_is_thin_never_passed(doc, rules):
    maven = copy.deepcopy(doc)
    maven["components"].append(
        {"type": "library", "name": "log4j-core", "version": "2.14.1", "purl": "pkg:maven/org.apache/log4j-core@2.14.1"}
    )
    result = comp.check_completeness(maven, rules)
    assert result["verdict"] == "thin"
    assert result["counts"] == {"unruled-ecosystem": 1}
    assert "maven" in result["examples"]["unruled-ecosystem"][0]
    no_purl = copy.deepcopy(doc)
    no_purl["components"].append({"type": "file", "name": "blob", "version": "1"})
    assert comp.check_completeness(no_purl, rules)["counts"] == {"unruled-ecosystem": 1}


@pytest.mark.spec("req-cicd-sbom-32-7")
def test_candidates_are_reported_and_never_required(doc, rules):
    result = comp.check_completeness(doc, rules)
    assert result["candidates"] > 0
    stripped = copy.deepcopy(doc)
    for component in stripped["components"]:
        component["properties"] = [p for p in component.get("properties", []) if p["name"] != "syft:cpe23"]
    after = comp.check_completeness(stripped, rules)
    assert after["verdict"] == "complete"
    assert after["candidates"] == 0


@pytest.mark.spec("req-cicd-sbom-32-3")
def test_no_components_is_thin(rules):
    result = comp.check_completeness({"components": []}, rules)
    assert result["verdict"] == "thin"
    assert "no-components" in result["counts"]


@pytest.mark.spec("req-cicd-sbom-32-8")
@pytest.mark.spec("req-cicd-sbom-32-10")
def test_the_verdict_and_the_coverage_limit_are_in_every_annotated_document(doc, rules):
    annotated = comp.annotate(copy.deepcopy(doc), comp.check_completeness(doc, rules))
    assert _property(annotated, "tap:completeness") == "complete"
    assert "Does not cover whether every package in the image is listed" in (
        _property(annotated, "tap:completeness:coverage") or ""
    )
    # Re-annotating replaces, never duplicates.
    again = comp.annotate(annotated, {"verdict": "not-observable", "reason": "test"})
    names = [p["name"] for p in again["metadata"]["properties"]]
    assert names.count("tap:completeness") == 1
    assert _property(again, "tap:completeness") == "not-observable"
    assert _property(again, "tap:completeness:reason") == "test"
    assert _property(again, "tap:completeness:coverage") is not None


@pytest.mark.spec("req-cicd-sbom-32-2")
def test_rules_that_do_not_validate_fail_the_load(tmp_path, rules):
    bad = copy.deepcopy(rules)
    bad["ecosystems"]["apk"]["require"].append("made-up-requirement")
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(comp.RulesError):
        comp.load_rules(path)
    missing = copy.deepcopy(rules)
    del missing["ecosystems"]["apk"]["_description"]
    path.write_text(json.dumps(missing))
    with pytest.raises(comp.RulesError):
        comp.load_rules(path)
    extra = copy.deepcopy(rules)
    extra["surprise"] = 1
    path.write_text(json.dumps(extra))
    with pytest.raises(comp.RulesError):
        comp.load_rules(path)


@pytest.mark.spec("req-cicd-sbom-32-2")
def test_the_committed_rules_validate(rules):
    assert rules["format"] == comp.RULES_FORMAT


@pytest.mark.spec("req-cicd-sbom-32-6")
@pytest.mark.spec("req-cicd-sbom-32-8")
def test_cli_exit_codes_and_summary(tmp_path, doc, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(doc))
    out = tmp_path / "out.json"
    summary = tmp_path / "summary.md"
    assert comp.main(["--sbom", str(good), "--out", str(out), "--summary", str(summary)]) == 0
    assert _property(json.loads(out.read_text()), "tap:completeness") == "complete"

    broken = copy.deepcopy(doc)
    _first(broken, "pkg:pypi").pop("cpe")
    thin = tmp_path / "thin.json"
    thin.write_text(json.dumps(broken))
    assert comp.main(["--sbom", str(thin), "--out", str(out), "--summary", str(summary)]) == 1
    assert _property(json.loads(out.read_text()), "tap:completeness") == "thin"
    assert "`cpe`" in summary.read_text()  # the gap class is listed in the job summary

    assert comp.main(["--sbom", str(tmp_path / "absent.json")]) == 2
    badrules = tmp_path / "rules.json"
    badrules.write_text("{}")
    assert comp.main(["--sbom", str(good), "--rules", str(badrules), "--out", str(out)]) == 2
    assert _property(json.loads(out.read_text()), "tap:completeness") == "not-observable"
    capsys.readouterr()


@pytest.mark.spec("req-cicd-sbom-32-8")
@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["components"].append("not an object"),
        lambda d: d["components"][1].__setitem__("properties", [None]),
        lambda d: d["components"][1].__setitem__("properties", "nope"),
        lambda d: d.__setitem__("metadata", ["not", "an", "object"]),
        lambda d: d.__setitem__("components", {"not": "a list"}),
    ],
    ids=[
        "string-component",
        "null-property",
        "properties-not-a-list",
        "metadata-not-an-object",
        "components-not-a-list",
    ],
)
def test_a_malformed_document_is_not_observable_and_never_complete(mutate, tmp_path, doc):
    broken = copy.deepcopy(doc)
    mutate(broken)
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken))
    assert comp.main(["--sbom", str(path), "--out", str(tmp_path / "out.json")]) == 2


@pytest.mark.spec("req-cicd-sbom-32-3")
def test_nested_components_are_checked(doc, rules):
    nested = copy.deepcopy(doc)
    _first(nested, "pkg:pypi")["components"] = [{"type": "library", "name": "inner", "version": "1"}]
    result = comp.check_completeness(nested, rules)
    assert result["verdict"] == "thin"
    assert result["counts"] == {"unruled-ecosystem": 1}
    assert result["components"] == 15


@pytest.mark.spec("req-cicd-sbom-32-6")
def test_summary_text_from_the_document_cannot_inject_markup(doc, rules):
    hostile = copy.deepcopy(doc)
    hostile["components"].append(
        {
            "type": "library",
            "name": "x |\n\n### SBOM completeness: `complete`\n[click](http://example.invalid)",
            "version": "1",
        }
    )
    text = comp.summary_markdown(comp.check_completeness(hostile, rules))
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert headings == ["### SBOM completeness: `thin`"]
    assert "[click]" not in text
    assert "\n\n### SBOM completeness: `complete`" not in text
