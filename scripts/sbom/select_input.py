"""Select the SBOM revision a rescan starts from: the highest VERIFIED one (req-cicd-sbom-20-10, -22).

For an image digest this verifies the image's CycloneDX attestations against the default-deny trust list
(`trusted-signers.json`), takes the predicate of the highest `version` among those that verify, and stages it as
`scan-inputs/sbom.cdx.json` for `merge_enrich.py`, with the facts about it in `scan-inputs/meta.json`.

Verification is delegated: each trusted signer is checked by `gh attestation verify` with `--cert-identity` (the exact
signer workflow and ref) and, where the entry pins one, `--signer-digest`. This code never reimplements a certificate
check (req-cicd-sbom-22-8); it reads what a successful verification returned.

The image and digest arrive in the IMAGE and DIGEST environment variables and are matched against strict patterns
before use; no file path comes from the environment, the command line or the documents.

Fails closed: an unreadable or empty trust list, no verifiable attestation, a subject digest that is not the one asked
for, or verified revisions that disagree on serialNumber each stop the run (req-cicd-sbom-22-1, -22-2).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
TRUSTED_SIGNERS = _HERE / "trusted-signers.json"
SIGNERS_SCHEMA = _HERE / "trusted-signers.schema.json"
OUTPUT_DIR = Path("scan-inputs")

PREDICATE_TYPE = "https://cyclonedx.org/bom"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._/-]*$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REGISTRY = "ghcr.io"


class SelectionError(Exception):
    """No revision can be selected: the run must fail."""


def load_signers() -> list[dict[str, Any]]:
    """The trusted signers, schema-validated; raises `SelectionError` on any failure (default deny)."""
    try:
        import jsonschema  # noqa: PLC0415 - imported here so a missing library is a SelectionError, not an ImportError
    except ImportError as exc:
        raise SelectionError(f"jsonschema is not importable, so the trust list cannot be validated: {exc}") from exc
    signers_doc: dict[str, Any]
    try:
        signers_doc = json.loads(TRUSTED_SIGNERS.read_text(encoding="utf-8"))
        schema = json.loads(SIGNERS_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SelectionError(f"cannot read the trust list or its schema: {exc}") from exc
    try:
        jsonschema.validate(signers_doc, schema)
    except jsonschema.ValidationError as exc:
        raise SelectionError(f"the trust list does not validate: {exc.message} at {list(exc.absolute_path)}") from exc
    signers: list[dict[str, Any]] = signers_doc["signers"]
    return signers


def verify_command(image: str, digest: str, signer: dict[str, Any]) -> list[str]:
    """The `gh attestation verify` argv for one trusted signer. Pure; no shell is involved."""
    identity = f"https://github.com/{signer['repository']}/{signer['workflow_path']}@{signer['ref']}"
    command = [
        "gh",
        "attestation",
        "verify",
        f"oci://{REGISTRY}/{image}@{digest}",
        "--owner",
        image.split("/", 1)[0],
        "--predicate-type",
        PREDICATE_TYPE,
        "--cert-identity",
        identity,
        "--cert-oidc-issuer",
        OIDC_ISSUER,
        "--format",
        "json",
    ]
    if signer.get("signer_digest"):
        command += ["--signer-digest", signer["signer_digest"]]
    return command


def canonical(value: Any) -> bytes:
    """One serialization for the attestation digest: sorted keys, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def signed_predicate_bytes(item: dict[str, Any], expected: dict[str, Any]) -> bytes:
    """The predicate exactly as signed: the bytes of the `predicate` value inside the DSSE payload.

    The content digest of a revision is the sha256 of these bytes — what was verified — never of a
    re-serialization. They are cut out of the in-toto statement by locating the value and decoding it in place, and
    must parse to the same document the verification returned, or the run stops.
    """
    try:
        payload = base64.b64decode(item["attestation"]["bundle"]["dsseEnvelope"]["payload"], validate=True).decode(
            "utf-8"
        )
        marker = payload.index('"predicate"')
        start = payload.index(":", marker) + 1
        while payload[start] in " \t\r\n":
            start += 1
        value, end = json.JSONDecoder().raw_decode(payload, start)
    except (KeyError, TypeError, ValueError) as exc:
        raise SelectionError(f"cannot cut the signed predicate out of the attestation payload: {exc}") from exc
    if value != expected:
        raise SelectionError("the predicate in the signed payload is not the document verification returned")
    return payload[start:end].encode("utf-8")


def _integrated_time(item: dict[str, Any]) -> int:
    try:
        entries = item["attestation"]["bundle"]["verificationMaterial"]["tlogEntries"]
        return int(entries[0]["integratedTime"])
    except KeyError, IndexError, TypeError, ValueError:
        return 0


def candidates_from(verified: list[Any], digest: str, signer_id: str) -> list[dict[str, Any]]:
    """The revisions in one verification result: version, serial, signature time, digests, the predicate."""
    found: list[dict[str, Any]] = []
    for item in verified:
        result = item.get("verificationResult") or {}
        statement = result.get("statement") or {}
        if statement.get("predicateType") != PREDICATE_TYPE:
            continue
        subjects = [(s.get("digest") or {}).get("sha256") for s in statement.get("subject") or []]
        if digest.removeprefix("sha256:") not in subjects:
            raise SelectionError(f"a verified attestation from {signer_id} is for a different subject digest")
        predicate = statement.get("predicate")
        if not isinstance(predicate, dict) or not isinstance(predicate.get("version"), int):
            raise SelectionError(
                f"a verified attestation from {signer_id} carries no CycloneDX document with a version"
            )
        signed = signed_predicate_bytes(item, predicate)
        found.append(
            {
                "signer": signer_id,
                "version": predicate["version"],
                "serial": predicate.get("serialNumber"),
                "integrated_time": _integrated_time(item),
                "content_digest": hashlib.sha256(signed).hexdigest(),
                "attestation_digest": hashlib.sha256(canonical(item.get("attestation"))).hexdigest(),
                "predicate_bytes": signed,
            }
        )
    return found


def choose(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """The highest version; ties by the later signature time, then by content digest (req-cicd-sbom-20-4)."""
    if not candidates:
        raise SelectionError("no attestation verified against the trust list")
    serials = {c["serial"] for c in candidates}
    if len(serials) != 1 or None in serials:
        raise SelectionError(f"verified revisions disagree on serialNumber: {sorted(map(str, serials))}")
    return max(candidates, key=lambda c: (c["version"], c["integrated_time"], c["content_digest"]))


def run_verify(command: list[str]) -> list[Any]:
    """Run one verification. A non-zero exit means nothing verified for this signer, which is not an error by itself."""
    completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603 - argv list, no shell
    if completed.returncode != 0:
        sys.stderr.write(f"no attestation verified for this signer (exit {completed.returncode})\n")
        return []
    parsed = json.loads(completed.stdout)
    return parsed if isinstance(parsed, list) else []


def main() -> int:
    image = os.environ.get("IMAGE", "")
    digest = os.environ.get("DIGEST", "")
    try:
        if not IMAGE_RE.fullmatch(image) or ".." in image:
            raise SelectionError("IMAGE is not a lowercase owner/name image path")
        if not DIGEST_RE.fullmatch(digest):
            raise SelectionError("DIGEST is not sha256:<64 hex>")
        candidates: list[dict[str, Any]] = []
        for signer in load_signers():
            sys.stderr.write(f"verifying against signer {signer['id']}\n")
            candidates += candidates_from(run_verify(verify_command(image, digest, signer)), digest, signer["id"])
        chosen = choose(candidates)
        OUTPUT_DIR.mkdir(exist_ok=True)
        (OUTPUT_DIR / "sbom.cdx.json").write_bytes(chosen["predicate_bytes"])
        meta = {
            "input_attestation_digest": f"sha256:{chosen['attestation_digest']}",
            "input_version": chosen["version"],
            "input_serial": chosen["serial"],
            "input_signer": chosen["signer"],
            "input_content_digest": f"sha256:{chosen['content_digest']}",
            "candidates_verified": len(candidates),
        }
        (OUTPUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    except (SelectionError, ValueError, OSError) as exc:
        sys.stderr.write(f"selection failed: {type(exc).__name__}: {exc}\n")
        return 2
    sys.stderr.write(
        f"selected revision {chosen['version']} of {chosen['serial']} signed by {chosen['signer']} "
        f"({len(candidates)} verified)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
