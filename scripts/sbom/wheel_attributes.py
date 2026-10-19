"""License and architecture for the locked Python components (req-cicd-sbom-33).

The published image has no installed Python packages: its venv is created at container start by `uv sync` from a wheel
cache seed (`/opt/uv-cache-seed`). So Syft reads `uv.lock`, and a lock entry carries neither a license nor an
architecture. The seed holds the unpacked wheels, each with a `*.dist-info/WHEEL` (the tags, hence the architecture) and
`METADATA` (the license). This module reads those headers and joins them, by PEP 503 name and version, onto the
components the lockfile already lists.

The seed is an ATTRIBUTE SOURCE only: it never adds, removes or re-versions a component (req-cicd-sbom-2 stands; the
seed is available bytes, not running software). A component with no matching wheel is declared unknown, with a
reason, never left silent (req-cicd-sbom-33-5). The purl is never changed: it is the identity and the join key for
Grype and the grid (req-cicd-sbom-33-4).

Everything here is a pure function over text and dicts except SEED_SCRIPT, the fixed script `generate.py` runs inside
the image under test to print the headers. No value from a document reaches a command.
"""

from __future__ import annotations

import re
from typing import Any

#: Run by `sh -c` inside the image being scanned. It prints, for each unpacked wheel in the seed, the headers this module
#: reads: `@@ <dist-info dir>`, then WHEEL's Tag and Root-Is-Purelib lines and METADATA's license headers. Header lines
#: only (METADATA's body ends at the first blank line) and each cut to 200 columns.
SEED_SCRIPT = r"""cd /opt/uv-cache-seed/archive-v0 2>/dev/null || exit 0
find . -maxdepth 3 -name '*.dist-info' | sort | while read -r d; do
  printf '@@ %s\n' "$(basename "$d")"
  grep -h -E '^(Tag|Root-Is-Purelib):' "$d/WHEEL" 2>/dev/null | cut -c1-200
  sed '/^$/q' "$d/METADATA" 2>/dev/null | grep -E '^(License-Expression:|License:|Classifier: License ::)' | cut -c1-200
done
"""

_MACHINE = re.compile(r"(aarch64|arm64|x86_64|amd64|i686|i386|ppc64le|s390x|armv7l)$")
_MACHINE_NAME = {"arm64": "aarch64", "amd64": "x86_64", "i386": "i686"}
_UNKNOWN_LICENSE = {"", "unknown", "none", "n/a"}

STATUS_PREFIXES = ("tap:license:", "tap:licenses:", "tap:python:", "tap:architecture")


def pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_seed_records(text: str) -> list[dict[str, Any]]:
    """The records `SEED_SCRIPT` printed: name, version, wheel tags, and the license headers of each dist-info."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("@@ "):
            dist = line[3:].removesuffix(".dist-info")
            name, _, version = dist.rpartition("-")
            if not name or not version:
                current = None
                continue
            current = {
                "name": name,
                "version": version,
                "tags": [],
                "expression": None,
                "license": None,
                "classifiers": [],
            }
            records.append(current)
        elif current is not None:
            if line.startswith("Tag: "):
                current["tags"].append(line[5:].strip())
            elif line.startswith("License-Expression: "):
                current["expression"] = line[len("License-Expression: ") :].strip() or None
            elif line.startswith("License: "):
                current["license"] = line[len("License: ") :].strip() or None
            elif line.startswith("Classifier: License :: "):
                current["classifiers"].append(line[len("Classifier: License :: ") :].strip())
    return records


def machine_from_tags(tags: list[str]) -> str | None:
    """`noarch` for an `any` platform tag, else the machine its platform tag names; None when it cannot be read."""
    machines: set[str] = set()
    for tag in tags:
        platform = tag.rsplit("-", 1)[-1]
        if platform == "any":
            machines.add("noarch")
            continue
        match = _MACHINE.search(platform)
        if match is None:
            return None
        machines.add(_MACHINE_NAME.get(match.group(1), match.group(1)))
    if not machines:
        return None
    return ",".join(sorted(machines))


def license_choice(record: dict[str, Any]) -> tuple[list[dict[str, Any]], str] | None:
    """CycloneDX `licenses` and which header supplied them: expression, license text, or classifier."""
    if record["expression"]:
        return [{"expression": record["expression"]}], "expression"
    text = record["license"]
    if text and text.strip().lower() not in _UNKNOWN_LICENSE:
        return [{"license": {"name": text}}], "license"
    names = [c.rsplit("::", 1)[-1].strip() for c in record["classifiers"] if c.strip()]
    names = [n for n in dict.fromkeys(names) if n]
    if names:
        return [{"license": {"name": n}} for n in names], "classifier"
    return None


def attributes_by_component(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """(PEP 503 name, version) to the record; the first of any duplicates wins, in the script's sorted order."""
    attributes: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        attributes.setdefault((pep503(record["name"]), record["version"]), record)
    return attributes


def _drop_attribute_properties(component: dict[str, Any]) -> list[dict[str, str]]:
    return [p for p in component.get("properties") or [] if not str(p.get("name", "")).startswith(STATUS_PREFIXES)]


def _is_pypi(component: dict[str, Any]) -> bool:
    return str(component.get("purl") or "").startswith("pkg:pypi/")


def apply_to_cyclonedx(cdx: dict[str, Any], attributes: dict[tuple[str, str], dict[str, Any]]) -> dict[str, int]:
    """Write license and architecture onto each pypi component; count matched and declared-unknown components."""
    counts = {"pypi": 0, "matched": 0, "licenses_unknown": 0, "architecture_unknown": 0}
    for component in cdx.get("components") or []:
        if not _is_pypi(component):
            continue
        counts["pypi"] += 1
        record = attributes.get((pep503(str(component.get("name"))), str(component.get("version"))))
        props = _drop_attribute_properties(component)
        if record is None:
            reason = "no matching wheel in the image's cache seed"
            props += [
                {"name": "tap:licenses:status", "value": "not-observed"},
                {"name": "tap:licenses:reason", "value": reason},
                {"name": "tap:architecture:status", "value": "not-observed"},
                {"name": "tap:architecture:reason", "value": reason},
            ]
            counts["licenses_unknown"] += 1
            counts["architecture_unknown"] += 1
        else:
            counts["matched"] += 1
            choice = license_choice(record)
            if choice is None:
                props += [
                    {"name": "tap:licenses:status", "value": "not-observed"},
                    {"name": "tap:licenses:reason", "value": "the wheel's metadata names no license"},
                ]
                counts["licenses_unknown"] += 1
            else:
                component["licenses"] = choice[0]
                props.append({"name": "tap:license:source", "value": choice[1]})
            machine = machine_from_tags(record["tags"])
            props.append({"name": "tap:python:wheel-tag", "value": ",".join(record["tags"])})
            if machine is None:
                props += [
                    {"name": "tap:architecture:status", "value": "not-observed"},
                    {"name": "tap:architecture:reason", "value": "the wheel's platform tag is not recognized"},
                ]
                counts["architecture_unknown"] += 1
            else:
                props.append({"name": "tap:architecture", "value": machine})
        component["properties"] = props
    return counts


def apply_to_spdx(spdx: dict[str, Any], attributes: dict[tuple[str, str], dict[str, Any]]) -> None:
    """`licenseDeclared` for each matched pypi package: the expression, or NOASSERTION (req-cicd-sbom-33-6)."""
    for package in spdx.get("packages") or []:
        purls = [
            r.get("referenceLocator", "") for r in package.get("externalRefs") or [] if r.get("referenceType") == "purl"
        ]
        if not any(str(p).startswith("pkg:pypi/") for p in purls):
            continue
        record = attributes.get((pep503(str(package.get("name"))), str(package.get("versionInfo"))))
        declared = record["expression"] if record and record["expression"] else "NOASSERTION"
        package["licenseDeclared"] = declared
