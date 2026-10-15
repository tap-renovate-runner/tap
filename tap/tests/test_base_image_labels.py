"""Each image records the base it was built on, derived from the one pin (`req-cicd-base-image-lifecycle-7`).

The Wolfi base is pinned `tag@digest` and rotates by Renovate. A label typed out beside the pin would be a
second copy that every Renovate bump leaves stale, so the Dockerfile writes the pin once, as the `WOLFI_BASE`
build ARG, and the `base` stage derives the two OCI base-image labels from it by variable expansion.

PROVEN HERE (text): one pin per Dockerfile, no literal base reference left on any `FROM`, the `base` stage
re-declares the ARG and derives both labels from it, and the two expansions yield a name and a digest when
evaluated on the pin. NOT PROVEN HERE: that BuildKit applies the expansion (observed on local builds of the
`base` stage of each image, 2026-10-15) and that Renovate still bumps the ARG (a manual Renovate run).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILES = {
    "web": _REPO_ROOT / "Dockerfile",
    "db": _REPO_ROOT / "docker" / "postgres" / "Dockerfile",
}
_PIN = re.compile(r"^ARG WOLFI_BASE=(?P<ref>\S+)$", re.MULTILINE)
_REFERENCE = re.compile(r"^[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}$")
_NAME_LABEL = 'org.opencontainers.image.base.name="${WOLFI_BASE%%@*}"'
_DIGEST_LABEL = 'org.opencontainers.image.base.digest="${WOLFI_BASE##*@}"'


def _text(image: str) -> str:
    return DOCKERFILES[image].read_text(encoding="utf-8")


def _from_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if re.match(r"^FROM\s", line)]


def _base_stage(text: str) -> str:
    start = text.index(" AS base\n")
    end = text.find("\nFROM ", start)
    return text[start : end if end != -1 else len(text)]


@pytest.mark.spec("req-cicd-base-image-lifecycle-7")
@pytest.mark.parametrize("image", sorted(DOCKERFILES))
def test_the_base_is_pinned_once_as_a_tag_at_digest_reference(image: str) -> None:
    pins = _PIN.findall(_text(image))
    assert len(pins) == 1, f"{image}: expected exactly one `ARG WOLFI_BASE=` pin, found {len(pins)}"
    assert _REFERENCE.match(pins[0]), f"{image}: {pins[0]!r} is not a tag@sha256 reference"


@pytest.mark.spec("req-cicd-base-image-lifecycle-7")
@pytest.mark.parametrize("image", sorted(DOCKERFILES))
def test_no_from_line_spells_the_base_out(image: str) -> None:
    text = _text(image)
    pin = _PIN.search(text)
    assert pin is not None
    spelled = [line for line in _from_lines(text) if "wolfi-base" in line or pin.group("ref") in line]
    assert spelled == [], f"{image}: FROM lines that repeat the base instead of using ${{WOLFI_BASE}}: {spelled}"
    assert any(line.startswith("FROM ${WOLFI_BASE} AS base") for line in _from_lines(text))


@pytest.mark.spec("req-cicd-base-image-lifecycle-7")
@pytest.mark.parametrize("image", sorted(DOCKERFILES))
def test_the_base_stage_derives_both_labels_from_the_pin(image: str) -> None:
    stage = _base_stage(_text(image))
    assert "\nARG WOLFI_BASE\n" in stage, f"{image}: the base stage must re-declare the ARG to read it"
    assert stage.index("\nARG WOLFI_BASE\n") < stage.index("LABEL org.opencontainers.image.base.name=")
    assert _NAME_LABEL in stage and _DIGEST_LABEL in stage


@pytest.mark.spec("req-cicd-base-image-lifecycle-7")
@pytest.mark.parametrize("image", sorted(DOCKERFILES))
def test_the_expansions_split_the_pin_into_a_name_and_a_digest(image: str) -> None:
    """`${v%%@*}` removes the longest suffix starting at `@`; `${v##*@}` removes the longest prefix ending at `@`."""
    ref = _PIN.search(_text(image)).group("ref")  # type: ignore[union-attr]
    name, _, digest = ref.partition("@")
    assert name.endswith(":latest") and name.startswith("cgr.dev/chainguard/wolfi-base")
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    assert ref.rsplit("@", 1)[0] == name and ref.rsplit("@", 1)[1] == digest
