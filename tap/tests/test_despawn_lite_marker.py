"""Despawn does not count the lite-spawn marker as uncommitted work (req-dev-multisession-teardown-safety-4).

`scripts/despawn-session.sh` cannot be sourced and tears down real containers, so these tests
do not run it end to end. They pull the exact dirty-check pipeline out of the script and run it
on sample `git status --porcelain` output, which is the only part this requirement changes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "despawn-session.sh"


def _filter() -> str:
    """The `| grep ...` stage that follows `status --porcelain` in the dirty check."""
    match = re.search(r'status --porcelain 2>/dev/null \| (grep [^\n)]*)\)"', SCRIPT.read_text(encoding="utf-8"))
    assert match, "the dirty check no longer filters the porcelain output"
    return match.group(1)


def _dirty_lines(porcelain: str) -> list[str]:
    run = subprocess.run(
        ["bash", "-c", _filter()], input=porcelain, capture_output=True, text=True, check=False
    )
    return [line for line in run.stdout.splitlines() if line]


@pytest.mark.spec("req-dev-multisession-teardown-safety-4")
def test_lite_marker_alone_is_clean() -> None:
    assert _dirty_lines("?? .lite-session\n") == []


@pytest.mark.spec("req-dev-multisession-teardown-safety-4")
@pytest.mark.parametrize(
    "line",
    [
        " M specs/spec-cicd-sbom.md",
        "?? boot/demo.boot.json",
        "?? .lite-session.bak",
        "?? sub/.lite-session",
        "A  .lite-session",
    ],
)
def test_anything_else_still_counts_as_dirty(line: str) -> None:
    assert _dirty_lines(f"?? .lite-session\n{line}\n") == [line]
