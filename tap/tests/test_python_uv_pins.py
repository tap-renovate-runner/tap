"""The Python and uv versions CI derives are pinned once, and agree with the image.

`req-dev-localexec-runner-interpreter-5/-6`. An open `requires-python` and a `setup-uv` with no
version let a uv release choose CI's Python overnight: uv 0.13.0 (2026-10-09) made 3.15 its
default download, plugin CI's tooling sync took CPython 3.15.0, and the locked closure had no
cp315 wheels (tap#1008). These tests read the real tree — `pyproject.toml`, the Dockerfile and
every workflow — so a bump that moves one of them without the others fails here.
"""

from __future__ import annotations

import re
import tomllib
from typing import Any

import pytest
import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from tap.guards.base import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
_SETUP_UV = "astral-sh/setup-uv@"
_CHECKOUT = "actions/checkout@"


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _dockerfile() -> str:
    return (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")


def _allowed_minors(spec: SpecifierSet) -> list[tuple[int, int]]:
    """The Python 3.x minors the specifier admits, probed at .0 and a late patch."""
    return [(3, m) for m in range(10, 40) if any(Version(f"3.{m}.{p}") in spec for p in (0, 99))]


def _image_python_minors() -> set[tuple[int, int]]:
    return {(3, int(m)) for m in re.findall(r"^\s+python-3\.(\d+)(?:-\w+)?=", _dockerfile(), re.MULTILINE)}


def _image_uv_version() -> Version:
    match = re.search(r"^COPY --from=ghcr\.io/astral-sh/uv:([0-9][^@\s]*)@sha256:", _dockerfile(), re.MULTILINE)
    assert match, "Dockerfile has no `COPY --from=ghcr.io/astral-sh/uv:<tag>@sha256:` line"
    return Version(match.group(1))


@pytest.mark.spec("req-dev-localexec-runner-interpreter-5")
def test_requires_python_admits_exactly_the_image_minor() -> None:
    spec = SpecifierSet(_pyproject()["project"]["requires-python"])
    minors = _allowed_minors(spec)
    assert len(minors) == 1, (
        f"requires-python `{spec}` admits {minors}; it must admit exactly one minor line, or a resolver "
        "takes the newest Python it can get (tap#1008)"
    )
    image = _image_python_minors()
    assert image == set(minors), (
        f"the Dockerfile installs python-3.N packages for {sorted(image)} but requires-python admits {minors}; "
        "move them together"
    )


@pytest.mark.spec("req-dev-localexec-runner-interpreter-5")
def test_the_open_floor_that_broke_ci_fails_the_check() -> None:
    assert len(_allowed_minors(SpecifierSet(">=3.14"))) > 1
    assert _allowed_minors(SpecifierSet(">=3.14,<3.15")) == [(3, 14)]


@pytest.mark.spec("req-dev-localexec-runner-interpreter-6")
def test_required_version_is_one_uv_minor_and_the_image_satisfies_it() -> None:
    raw = _pyproject()["tool"]["uv"].get("required-version")
    assert raw, "[tool.uv] required-version is unset: setup-uv falls back to `latest` (tap#1008)"
    spec = SpecifierSet(raw)
    image = _image_uv_version()
    assert image in spec, f"the Dockerfile's uv {image} does not satisfy required-version `{spec}`"
    next_minor = Version(f"{image.major}.{image.minor + 1}.0")
    assert next_minor not in spec, f"required-version `{spec}` admits uv {next_minor}: bound it to one minor"


def _puts_this_repo_at_root(step: Any) -> bool:
    """True when this step is a checkout of THIS repository at the workspace root."""
    if not (isinstance(step, dict) and str(step.get("uses", "")).startswith(_CHECKOUT)):
        return False
    with_block = step.get("with") or {}
    repo = str(with_block.get("repository", "")).strip()
    return with_block.get("path") in (None, "", ".") and repo in ("", "${{ github.repository }}")


def setup_uv_problems(name: str, data: dict[str, Any]) -> list[str]:
    """Every setup-uv step that does not derive uv's version from a pyproject.

    Order matters: setup-uv reads the root pyproject when it RUNS, so only a root checkout of
    this repository in an EARLIER step counts. Limit, named: a `version-file` is accepted on
    its path suffix alone. Which repository sits at that path (`_tooling`'s is a workflow
    input) cannot be resolved from the YAML.
    """
    problems: list[str] = []
    for job_name, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        root_ok = False
        for index, step in enumerate(job.get("steps") or []):
            if _puts_this_repo_at_root(step):
                root_ok = True
                continue
            if not (isinstance(step, dict) and str(step.get("uses", "")).startswith(_SETUP_UV)):
                continue
            with_block = step.get("with") or {}
            where = f"{name} job `{job_name}` step {index + 1}"
            if "version" in with_block:
                problems.append(f"{where}: a `version:` literal — derive it from required-version")
            elif not str(with_block.get("version-file", "")).endswith("pyproject.toml") and not root_ok:
                problems.append(
                    f"{where}: no earlier step checks this repository out at the workspace root and there "
                    "is no `version-file` naming a pyproject.toml, so setup-uv installs `latest`"
                )
    return problems


@pytest.mark.spec("req-dev-localexec-runner-interpreter-6")
def test_every_setup_uv_step_derives_its_version() -> None:
    problems: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            problems.extend(setup_uv_problems(path.name, data))
    assert not problems, "\n".join(problems)


@pytest.mark.spec("req-dev-localexec-runner-interpreter-6")
def test_the_unpinned_plugin_job_that_broke_fails_the_check() -> None:
    """The pre-tap#1008 plugin-ci shape: plugin checkout at the root, core at _tooling, bare setup-uv."""
    sha = "0" * 40
    broken = yaml.safe_load(f"""
jobs:
  tooling:
    steps:
      - uses: {_CHECKOUT}{sha}
        with: {{repository: "${{{{ inputs.plugin_repo }}}}", path: plugin}}
      - uses: {_CHECKOUT}{sha}
        with: {{repository: "${{{{ inputs.harness_repo }}}}", path: _tooling}}
      - uses: {_SETUP_UV}{sha}
""")
    assert setup_uv_problems("plugin-ci.yml", broken)
    broken["jobs"]["tooling"]["steps"][2]["with"] = {"version-file": "_tooling/pyproject.toml"}
    assert setup_uv_problems("plugin-ci.yml", broken) == []
    broken["jobs"]["tooling"]["steps"][2]["with"] = {"version": "0.12.20"}
    assert setup_uv_problems("plugin-ci.yml", broken)


@pytest.mark.spec("req-dev-localexec-runner-interpreter-6")
def test_a_root_checkout_after_setup_uv_does_not_count() -> None:
    sha = "0" * 40
    late = yaml.safe_load(f"""
jobs:
  j:
    steps:
      - uses: {_SETUP_UV}{sha}
      - uses: {_CHECKOUT}{sha}
""")
    assert setup_uv_problems("wf.yml", late)
    late["jobs"]["j"]["steps"].reverse()
    assert setup_uv_problems("wf.yml", late) == []
