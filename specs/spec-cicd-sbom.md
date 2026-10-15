# SBOM Emission Specification

## Philosophy

An SBOM (software bill of materials) is the machine-readable answer to "what exactly is
inside this artifact?" — per-component, per-version, diffable, consumable by scanners and
by Player-3 tooling without pulling the image apart. TAP's publish pipeline already proves
*who* built an artifact and *from which commit* (SLSA provenance,
`req-cicd-supply-chain-provenance`); the SBOM is the missing *what*.

Three facts, all established empirically (see
[doc-cicd-sbom-groundwork](../docs/misc/doc-cicd-sbom-groundwork.md)), shape every
requirement below:

1. **The published artifact is the version pin.** The OS package layer floats against
   rolling Wolfi at build time (`req-cicd-product-releases-3` groundwork): a version's
   images are that commit's source × the build day's packages, and a rebuild is not
   reproducible. Only an SBOM captured at build time records which packages a release
   actually shipped — release notes describe source changes; the package delta rides
   silently without it.
2. **The obvious one-liner produces a wrong SBOM for our images.** BuildKit's `sbom: true`
   runs a scanner locked to installed-package cataloging. Our web image deliberately
   contains no installed Python environment (wheel-cache + runtime `uv sync`), so the
   default scan misses the real closure (`uv.lock` is never parsed), inventories the wheel
   cache as ~101 phantom "installed" packages (missing `tap` itself; including build
   backends at multiple versions and a literal `my-test-package` test fixture), and drowns
   the result in ~1,012 Rust-crate entries from the `uv` binary. A plausible-but-wrong
   SBOM is worse than none: consumers diffing releases would chase ghosts.
3. **No scanner can see a hand-built component.** The single most compliance-significant
   binary in the image — the self-built OpenSSL 3.0.9 FIPS provider (`fips.so`, CMVP
   #4282) — appears in no package database and therefore in no scanned inventory. Honest
   SBOMs for TAP require deliberate augmentation, not just scanning.

The prior-art consensus (Kubernetes `bom`, Chainguard/apko, the cosign `attach sbom`
deprecation, GitHub's generate-and-attest flow) reduces to: **curate the generation, sign
the result, keep per-arch SBOMs standalone** — and TAP's digest-threading law
(`req-cicd-supply-chain-provenance-1`) extends unchanged: no mutable-name hop between
generation and signature.

Scope: the published `tap-web` and `tap-db` images today, extensible to **flavored
ready-made images** tomorrow (req-cicd-sbom-9). The durable boundary is NOT "core vs
plugins" — it is **baked-into-the-artifact vs added-at-runtime**: the image SBOM is the
*artifact-level* BOM (what every copy of this version contains everywhere); the boot
record is the *instance-level* BOM (what this running instance actually loaded). A
ready-made image that bakes a boot profile's plugin set moves that plugin closure across
the boundary — into the artifact, and therefore into its SBOM. Runtime-added plugins
remain the boot record's territory. The two compose; neither substitutes for the other.

## Goals

|   |   |   |
| :---: | --- | --- |
| 1. | Honest | The SBOM lists what the artifact actually carries — the true locked closure, no phantoms, hand-built components included |
| 2. | Signed | SBOMs travel only as signed attestations bound to content digests; an unsigned SBOM is a rumor |
| 3. | Diffable | SBOM(vN) − SBOM(vN−1) is the mechanical answer to "what changed under the version bump" — the upgrade-diff promise made machine-checkable |
| 4. | Guarded | A regression to a wrong-but-plausible SBOM fails the publish, loudly — accuracy is load-bearing, never accidental |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-cicd-sbom-1 | [Curated Standalone Generation](#curated-standalone-generation) | Implemented | Pinned standalone Syft against verified per-arch digests; BuildKit `sbom: true` is FORBIDDEN for these images |
| req-cicd-sbom-2 | [Closure Accuracy](#closure-accuracy) | Implemented | Locked Python closure IN (uv.lock cataloger); wheel-cache + uv-binary phantoms OUT (path excludes) |
| req-cicd-sbom-3 | [Out-of-Band Components Declared](#out-of-band-components-declared) | Implemented | Anything entering the image outside a package manager gets a hand-authored entry — first: `fips.so` (OpenSSL 3.0.9, CMVP #4282) |
| req-cicd-sbom-4 | [Signed Digest-Bound Home](#signed-digest-bound-home) | Implemented | `actions/attest` (sbom-path) per arch digest, GitHub attestation store; digest-threading law applies end to end; registry copy (if ever) must be a signed attestation, never an attachment; **a versioned release verifies them before it is tagged, and `:latest` moves only after they exist** (tap#525) |
| req-cicd-sbom-5 | [Per-Arch Standalone SBOMs](#per-arch-standalone-sboms) | Implemented | One SBOM per platform digest; no merged index-level SBOM exists |
| req-cicd-sbom-6 | [Single Derivation, Format as Serialization](#single-derivation-format-as-serialization) | Implemented | One Syft scan per digest is canonical; CycloneDX JSON + SPDX JSON BOTH emitted from that same scan on day one; CycloneDX primary |
| req-cicd-sbom-7 | [Canary Guard](#canary-guard) | Implemented | Fail-closed publish check: expected components present, known phantoms absent — else no attestation |
| req-cicd-sbom-8 | [Release SBOM Diffs](#release-sbom-diffs) | Backlog | Human-readable package delta per release, feeding the customer upgrade-diff contract; consumer of 1–7, not a blocker |
| req-cicd-sbom-9 | [Flavored Ready-Made Images](#flavored-ready-made-images) | Proposed | Design constraint now, implementation with the appliance-image work: an image baking a boot profile's plugins ships an SBOM covering core + baked plugin closure, from the same declared-manifest principle |
| req-cicd-sbom-10 | [Plugin-Declared SBOMs](#plugin-declared-sboms) | Implemented | Declare-vs-decide: plugin release CI declares an attested per-release SBOM; the system verifies and composes, never re-derives blindly; bake-time combined lock is the single derivation for flavored images |
| req-cicd-sbom-11 | [Standards Conformance Validation](#standards-conformance-validation) | Implemented | Schema-validate the CycloneDX document + fail-closed minimum-elements field checks (CISA/NSA 2026); canaries catch TAP-specific lies, this catches malformed valid-looking SBOMs |
| req-cicd-sbom-12 | [Out-of-Band Detection Gate](#out-of-band-detection-gate) | Implemented | Declaration is DETECTED, never remembered — all three pieces live: Dockerfile COPY --from reconciliation fail-closed per-commit (PATHS: that every site is declared — the declared VERSION is not reconciled here because it is no longer declared, it is derived, req-cicd-sbom-3-4); unknowns budget fail-closed per-publish per-arch (flipped on a proven 0/0/0/0); source-built set derived from no-binary-package + sdist-only lock entries and marked at generation, fail-closed on absence |
| req-cicd-sbom-13 | [Ecosystem Coverage](#ecosystem-coverage) | Implemented | Doctrine: adopt each ecosystem's OWN distribution system and merge at the lockfile seam. JS gap CLOSED: package-lock + `npm ci --ignore-scripts` js-vendor stage, all five files hash-matched upstream (no forks), echarts XSS surfaced+fixed by the native tooling on day one; hand-authored manifests remain last-resort named debt |
| req-cicd-sbom-14 | [Consumer Verification Docs](#consumer-verification-docs) | Proposed | The req-cicd-sbom-5 resolve-and-verify flow carried verbatim in the release/consumer documentation, once that surface exists |
| req-cicd-sbom-15 | [Plugin SBOM Composition](#plugin-sbom-composition) | Proposed | The composition half of -10: bake-time single derivation reconciled against plugin-declared SBOMs; boot records reference release SBOMs by digest — rides the appliance arc with -9 |
| req-cicd-sbom-16 | [Crypto Bill of Materials (CBOM) in the Image SBOM](#crypto-bill-of-materials-cbom-in-the-image-sbom) | Proposed | Close the CBOM gap inside the existing single derivation: `tap.crypto_bom` findings and dispositions ride the attested CycloneDX document as `tap:crypto:*` properties on the owning component; one document, one predicate. Providers only in the first slice; other assetTypes named, sourced and deferred. Ingestion verifies the attestation before it parses. |

---

### Curated Standalone Generation
----
RID: `req-cicd-sbom-1`

Status: `Implemented`

Trace: `non-python` — scripts/sbom/generate.py

SBOMs for the published images MUST be generated by a **pinned standalone Syft**
invocation running as a publish-pipeline step, scanning each **verified per-arch digest**
(the digests the merge step verified under `req-cicd-supply-chain-provenance-1`).

BuildKit's built-in generator (`sbom: true` on the build step) is **FORBIDDEN** for these
images and MUST NOT be enabled: `buildkit-syft-scanner` hardcodes installed-only
catalogers (all cataloger-selection overrides verified inert), pins an older Syft, and —
against our venv-less image layout — emits the phantom inventory described in the
Philosophy. This is not a preference; enabling it would publish a wrong SBOM that no
downstream consumer could distinguish from a right one.

The Syft version is pinned and Renovate-managed like every other pipeline dependency;
bumps ride PRs, never floats.

### Closure Accuracy
----
RID: `req-cicd-sbom-2`

Status: `Implemented`

Trace: `non-python` — scripts/sbom/generate.py

The web image's SBOM MUST contain the **locked Python closure** — the packages `uv.lock`
resolves, which are byte-for-byte what runtime `uv sync` installs — sourced via Syft's
declared-package (lockfile) cataloger explicitly enabled for the scan.

The SBOM MUST NOT contain the wheel-cache or tool-binary phantom inventory. At minimum
the scan excludes `/opt/uv-cache-seed/**` (unpacked-wheel `dist-info` masquerading as
installed packages: build backends, vendored internals, multi-version duplicates, test
fixtures) and the ~1,012 Rust-crate entries of **embedded cargo-auditable metadata**
inside the `uv`/`uvx` binaries — the tool's own dependency closure, not the artifact's.
The exclusion is the embedded *metadata*, NEVER the executables themselves: `uv` and
`uvx` are real, load-bearing components of the image and MUST appear in the SBOM — as
declared out-of-band entries under req-cicd-sbom-3, since they arrive by digest-pinned
`COPY --from` rather than a package manager. Rationale for the cache exclusion: the
cache is *available bytes*, not *running software*; its inventory approximates the
closure while missing real members (`colorama`, `tzdata`, `tap` itself) and adding ~31
phantoms — and it vanishes entirely if the cache-seeding strategy changes. An SBOM must
never be load-bearing on an accident.

### Out-of-Band Components Declared
----
RID: `req-cicd-sbom-3`

Status: `Implemented`

Any component that enters a published image **outside a package manager** — compiled from
source in a build stage, copied from a builder, vendored by hand — MUST be declared in
the SBOM via a hand-authored supplemental entry, maintained alongside the Dockerfile that
introduces it.

First and motivating member: the self-built OpenSSL **3.0.9 FIPS provider**
(`/usr/lib/ossl-modules/fips.so`, CMVP certificate #4282) in both images. No scanner can
infer it (verified: it surfaces only as an uncataloged-file unknown), yet it is the most
compliance-significant binary TAP ships. Its SBOM entry is the first machine-readable
artifact of the crypto-BOM discipline (`req-fips-crypto-bom`, spec-fips.md): the crypto
provider inventory, in a standard format, per artifact.

Second members: the **`uv` and `uvx` executables** in the web image, copied by
digest-pinned `COPY --from` from the upstream `ghcr.io/astral-sh/uv` image — outside any
package manager, therefore declared. (Their ~1,012 embedded cargo-auditable crate entries
stay excluded under req-cicd-sbom-2; the executables do not.)

Each SBOM entry carries, at minimum: component name, **version**, **source** (for
copied binaries: the upstream image ref + digest; for self-built: the pinned source URL),
**file path in the image**, **SHA-256 of the file**, **license**, and a **purl/CPE where
one exists**.

**Which of those the manifest AUTHORS, and which generation DERIVES** (tap#225). The
manifest declares what only a human can say — identity, path, license, rationale, the
version-free `purl_base`. Every fact the build already states is derived at generation
time and MUST NOT appear in the manifest:

| Fact | Authoring site | How the entry gets it |
| --- | --- | --- |
| file SHA-256 | the built artifact | hashed from the scanned image, per-arch |
| copied-image version + source ref + purl | the `COPY --from=<repo>:<tag>@sha256:<digest>` line | `generate.derive_copied_image_facts` joins manifest→Dockerfile on `path` |
| self-built FIPS provider version | `docker/build-openssl-fips.sh` (`OSSL_VERSION`) | `tap/fips_pins.py`; the manifest's `version`, `source`, `purl` and `cpe` are **verified** against it and fail closed |

The derivation is remedy #1 of *derive > verify > detect*: the second copy is removed, so
it cannot drift. It was not a hypothetical. The supplemental declared `uv` **0.12.3**,
with a digest to match, while the image shipped 0.12.7 and then 0.12.15 — Renovate's
`dockerfile` manager bumps the pin and nothing bumped the manifest, so the published,
**attested** SBOM asserted contents that were not in the image and grew more wrong with
every release. The reconciliation gate (req-cicd-sbom-12) did not catch it because it
checks that every `COPY` path is DECLARED, never that the declared version is TRUE: a
presence test wearing a correctness test's clothes.

The manifest's own `_description` had predicted the failure ("Version must match the
Dockerfile COPY pin (reconciled by the req-cicd-sbom-12 guard when it lands)") and the
note outlived the guard's landing. Deriving retires the note rather than delivering the
reconciliation it anticipated — and it is the decision this file had already made once,
for the file hash, and stopped one field short of.

The self-built provider keeps authored `source`/`purl`/`cpe` on purpose: the release-URL
shape is constructed once in `docker/build-openssl-fips.sh` from `OSSL_VERSION`, and
restating that construction in Python would trade one duplicate for another across a
language boundary. The fact that drifts — the version — is derived from the pin, and the
three fields that spell it out are checked against it. `OSSL_SHA256` and
`OSSL_SIGNING_PRIMARY` stay hand-authored because they are **assertions, not copies**: a
digest derived from the file it checks verifies nothing.

The declarations are **one small structured supplemental-manifest format** — not prose,
not per-entry ad-hoc files: a single manifest per image, living alongside the Dockerfile
that introduces its components (so a digest-pin bump and its SBOM entry change in the
same diff), **validated against a committed JSON Schema at load** (the standing TAP rule
for structured formats: schema + loader validation + descriptions on the top level and
every entry, for AI and security readers), **merged into the generated CycloneDX during
the single derivation** (req-cicd-sbom-1/-6 — the merge is part of generation, never a
post-hoc edit to an attested document), and covered both ways: canaries (req-cicd-sbom-7)
prove the merged entries survived into the output; the detection gate (req-cicd-sbom-12)
proves the manifest matches what the Dockerfiles actually introduce. A schema-invalid
manifest fails the publish exactly like a failed canary.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-3-1 | Committed manifests validate | Implemented | Both images' committed supplemental manifests load and validate against the committed JSON Schema. | |
| req-cicd-sbom-3-2 | Schema failure is loud | Implemented | A manifest missing a required field fails the loader with a validation error, never a silent skip. | |
| req-cicd-sbom-3-3 | Injection carries the fields | Implemented | Injected components survive CycloneDX and SPDX schema validation carrying artifact-computed hashes, sources, and the coverage statement. | |
| req-cicd-sbom-3-4 | Copied-image facts are derived | Implemented | A copied-image component's version, source ref and purl are derived at generation time from the `COPY --from` pin that lands its path — never read from the manifest. A bumped pin therefore produces a correct SBOM with no second edit. | tap#225: the declared uv version was four releases stale in a published, attested SBOM. `generate.derive_copied_image_facts`; `tap/tests/test_sbom_generate.py`. |
| req-cicd-sbom-3-5 | Authoring a derived fact is a red | Implemented | A copied-image entry that declares `version`, `source` or `purl` fails BOTH the JSON Schema and the generator, and a declared path fails the generator unless EXACTLY ONE `COPY --from` site writes it and that site is a fully pinned `<repo>:<tag>@sha256:<digest>` image — a half-pinned or stage-name reference is never treated as a version, and two sources writing one path is refused rather than resolved. | Removing the copy only helps if it cannot come back; the second half of this is the "NOT OBSERVABLE is not absent" rule — an underivable component must not publish as though its provenance were known. The parser reads instructions, not the stage graph, so it cannot say which of two writers ships; picking the textually last one would be an assumption dressed as a derivation (Codex review seat, PR# 627 - tap). Residuals, named not implied: a plain `COPY` from the build context over a declared path is invisible to it (tap#642), and the tag a version is read from is not itself proven to match the digest's bytes (tap#643). |
| req-cicd-sbom-3-6 | Self-built version claims are verified | Implemented | For the self-built FIPS provider the manifest's `version`, and every version-bearing identity field (`source`, `purl`, `cpe`), are compared against the pin in `docker/build-openssl-fips.sh` and fail closed on disagreement. | Remedy #2 where #1 does not fit; a stale `cpe` is the worst of the three, since it silently matches the advisory feed for a version the image does not ship. |

This requirement is the general rule; the guard for it is req-cicd-sbom-7's canary check
(a missing declared component fails the publish).

### Signed Digest-Bound Home
----
RID: `req-cicd-sbom-4`

Status: `Implemented`

Trace: `non-python` — .github/workflows/publish-images.yml

SBOMs are published as **signed attestations in the GitHub attestation store**
(`actions/attest` with `sbom-path` — the boring-current action; `actions/attest-sbom`
is deprecated in its favor), subject = the verified per-arch image digest — the same home,
identity root, and `gh attestation verify` story as the existing SLSA provenance. No new
trust roots.

The digest-threading law (`req-cicd-supply-chain-provenance-1`) extends to SBOMs: between
generation and signature the SBOM and its subject MUST never be referenced through a
mutable name. The scan targets `ref@digest`; the attestation subject is that same digest;
the document travels within one job (or via integrity-held workflow artifacts, never via
registry round-trip).

Since tap#507 the document DOES travel by artifact: generation runs on a read-only token
(`sbom` job) and signing in a first-party-only job (`attest-sbom`), so no third-party code
shares the signing token. The signing job re-binds before it signs, fail-closed: each
document must name, in its own content, the image ref and the exact per-arch digest it is
about to be attested against (CycloneDX `metadata.component`; SPDX's DESCRIBES-ed CONTAINER
package). Residual, named: the split protects the token, not the content — a compromised
generation dependency could still produce a false document bound to the right subject.

**The release gate (tap#525, 2026-09-19).** Producing an attestation and *releasing only
what carries one* are two different guarantees, and TAP had only the first. `publish-release-tags`
polled until `:sha-<short>` EXISTED and promoted it to `:X.Y.Z` — presence read as completeness —
so for 15 days (tap#518), and again on the next change (tap#543), versioned tags were cut from
images whose SBOM attestations had never been produced, with every workflow green. Two changes
close that:

- **Before a version tag is created**, `retag` verifies SLSA provenance on the index digest and
  BOTH SBOM predicates on every per-arch child (`gh attestation verify --predicate-type`), and
  refuses otherwise. Three states, two of which block: *verified*; *MISSING* (the subject exists,
  the attestations API answers 404); *NOT OBSERVABLE* (the check could not complete). A check that
  could not look must never render as nothing-to-find. Counts are not a verdict — an unchanged
  image is re-attested on every publish, so ≥1 verifying bundle is the predicate.
- **`:latest` moves last**, in `promote-latest`, which waits on `attest-sbom`. `:sha-<short>` is
  still minted by the merge step because an OCI index cannot exist untagged and every attestation
  binds to those digests; the mutable pointer consumers follow is what waits.

Neither workflow can be exercised by PR CI (tag-push and main-push triggers), which is how both
failures shipped green; `tap/tests/test_release_gates.py` asserts the ordering statically and
executes the gate's own `run:` body against stub `docker`/`gh` to prove all three outcomes.

The registry-side copy landed WITH the GitHub home rather than as a deferral:
`actions/attest`'s `push-to-registry: true` pushes the identical Sigstore-signed
bundle to GHCR as an OCI referrer (matching the provenance step's existing behavior)
— the signed form, satisfying the mirrored/air-gapped consumer without any second
signing mechanism. An unsigned attachment remains forbidden: the ecosystem
deprecated `cosign attach sbom` for exactly the trust gap TAP's posture forbids.

### Per-Arch Standalone SBOMs
----
RID: `req-cicd-sbom-5`

Status: `Implemented`

Trace: `non-python` — .github/workflows/publish-images.yml

Each platform variant (amd64, arm64) carries its **own standalone SBOM**, attested
against its own digest. No merged index-level SBOM is produced. Rationale (prior-art
consensus): consumers can and do pull a platform manifest directly, so its SBOM must
stand alone; and the per-arch closures genuinely differ (compiled wheels, arch-specific
apk packages). The multi-arch answer is "ask for the platform you run," not a synthetic
union document.

A consumer starting from a version tag MUST have a written, exact resolve-and-verify
path — the two-step flow below is canonical. (Carrying it verbatim in the
release/consumer documentation is req-cicd-sbom-14 — a docs surface that does not
exist yet; a per-arch design without the written path just relocates the confusion.)

```bash
# 1. Resolve the version tag to YOUR platform's digest (the SBOM subject):
docker buildx imagetools inspect ghcr.io/unified-systems-com/tap-web:X.Y.Z \
  --format '{{json .Manifest}}' \
  | jq -r '.manifests[] | select(.platform.os=="linux" and .platform.architecture=="arm64") | .digest'

# 2. Verify the SBOM attestation FOR THAT DIGEST. The --predicate-type flag is
#    REQUIRED: `gh attestation verify` defaults to SLSA provenance and will not
#    find an SBOM attestation without it.
gh attestation verify oci://ghcr.io/unified-systems-com/tap-web@sha256:<digest> \
  --owner unified-systems-com \
  --predicate-type https://cyclonedx.org/bom          # primary (CycloneDX)
#   --predicate-type https://spdx.dev/Document/v2.3   # the SPDX serialization
# (Use the EXACT predicate URI the attestation was emitted with — for SPDX 2.3
#  that is the versioned https://spdx.dev/Document/v2.3, not the bare form.)
```

(The plain provenance verify, no `--predicate-type`, continues to work unchanged for
"who built this"; the SBOM predicate answers "what is inside it." Same digest, two
questions, two predicates.)

### Single Derivation, Format as Serialization
----
RID: `req-cicd-sbom-6`

Status: `Implemented`

Trace: `non-python` — scripts/sbom/generate.py

One Syft scan per digest is the **single derivation**; formats are serializations of it.
BOTH standard formats are emitted from that same scan, immediately: **CycloneDX JSON as
primary** (security-consumer gravity: Dependency-Track, VEX-aware triage, Trivy/Grype
native) and **SPDX JSON alongside it** (government/legal gravity; the format BuildKit
emits and Kubernetes' `bom` is built on — dull interoperability is the point of an
SBOM). Both ride the same signed attestation home (req-cicd-sbom-4) against the same
digest; both schema-validate under req-cicd-sbom-11, with the full minimum-elements
battery running on the primary. What remains FORBIDDEN is a second independent scan —
two scanners drift, and a consumer holding both learns nothing except that we disagree
with ourselves. The derive-once rule, applied to CI artifacts: one derivation, two
serializations, zero disagreement by construction.

### Canary Guard
----
RID: `req-cicd-sbom-7`

Status: `Implemented`

Before attesting, the pipeline MUST verify each generated SBOM **fail-closed** against a
canary list, refusing to publish on any miss:

* web MUST contain: `tap` at the built version, `django`, a known apk canary (e.g.
  `openssl`), and **every declared out-of-band component** (req-cicd-sbom-3: `fips.so`,
  `uv`, `uvx`);
* db MUST contain: `postgresql-16` and its declared out-of-band component (`fips.so`);
* both MUST NOT contain known-phantom markers (e.g. `my-test-package`, any
  `/opt/uv-cache-seed` location).

Rationale: every failure mode observed in the groundwork was *silent plausibility* — a
scan that succeeds and emits confident garbage. The canary guard converts "the SBOM
quietly went wrong" (cataloger regressed in a Syft bump, cache path moved, augmentation
step dropped) into a red publish. Canaries are deliberately TAP-specific truths; generic
structural well-formedness is req-cicd-sbom-11's job — the two validate different
failure classes at the same gate point. At implementation time this check is a validation
surface and gets its Validation Map row (spec-dev-validation.md) in the same change.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-7-1 | Honest document passes | Implemented | A document carrying the required canaries and every declared out-of-band component passes. | |
| req-cicd-sbom-7-2 | Dropped declaration is a red | Implemented | Omitting any declared out-of-band component (fips.so, uv, uvx) fails the guard. | |
| req-cicd-sbom-7-3 | Missing tap itself is a red | Implemented | A plausible SBOM missing the `tap` component fails. | |
| req-cicd-sbom-7-4 | Phantoms are a red | Implemented | A known phantom name or a component located under the wheel-cache path fails. | |

### Release SBOM Diffs
----
RID: `req-cicd-sbom-8`

Status: `Backlog`

A human-readable package delta between consecutive release SBOMs (added / removed /
version-changed, OS layer and Python closure), attached to the release. This is the
machine-checkable half of the customer upgrade-diff promise: release notes describe
source changes; the SBOM diff surfaces the silent package drift underneath
(`req-cicd-product-releases`). Deferred: pure consumer of req-cicd-sbom-1..7, adds no
constraint on them, and should be built against real release cadence.

### Flavored Ready-Made Images
----
RID: `req-cicd-sbom-9`

Status: `Proposed`

TAP is tacking toward **ready-made appliance images**: a boot profile's plugin set baked
into a published image (e.g. a GitHub-configuration mapping instance), pulled from the
registry with everything installed — an adopter slots in secrets and boots. This
requirement is a **design constraint on req-cicd-sbom-1..7 now** and an implementation
obligation when those images ship:

* A flavored image's SBOM MUST cover the core closure **plus the baked plugin closure**
  (each plugin and its dependencies), derived by the same principle as everything else:
  from **declared, hash-verified manifests baked in the artifact** — the core `uv.lock`
  plus the flavor's boot-profile plugin manifest (the boot-record-as-BOM data, which
  already names each plugin at an exact version) — never by scanning materialized
  caches or installed trees (the wheel-cache phantom lesson applies with more force,
  since plugin wheels ride the same cache mechanism).
* Therefore the generation step (req-cicd-sbom-1) MUST be parameterized as *artifact ×
  list-of-declared-manifests*, not hardcoded to "two images, one lockfile each"; the
  canary guard (req-cicd-sbom-7) MUST take per-flavor canary lists (every baked plugin
  present; the flavor's profile named).
* The boot record of a ready-made instance SHOULD reference the image SBOM (by image
  digest) for the baked set rather than restating it, and record only runtime deltas —
  one fact, derived once, linked across layers.
* Naming/tagging of flavored images follows the existing pipeline disciplines unchanged
  (digest-threading, per-arch, signed attestation home).

Status rationale: no flavored image exists yet, so nothing here is buildable — but
req-cicd-sbom-1/-7's implementation must not foreclose it. The extensibility is cheap at
design time and expensive to retrofit (the security-posture asymmetry).

### Plugin-Declared SBOMs
----
RID: `req-cicd-sbom-10`

Status: `Implemented`

**Declaration half BUILT and live-proven 2026-08-20**: the reusable release lane
(`.github/workflows/plugin-release-sbom.yml` + `scripts/sbom/plugin_release.py`) is
wired as a tag-triggered thin caller in ALL 12 plugin repos; pilot release
tap-plugin-aws-core v0.4.2 carries verified wheel provenance + both SBOM attestation
predicates (`gh attestation verify <wheel> --owner unified-systems-com [--predicate-type …]`). A wheel SBOM covers the plugin at its exact version plus
DECLARED dependency requirements — resolution deliberately absent (coverage statement
says where resolution truth lives). This requirement is scoped to the
DECLARATION half; the composition half (flavored-image bake-time derivation + boot
records referencing release SBOMs by digest) is req-cicd-sbom-15, riding the appliance
arc with req-cicd-sbom-9. Named gap CLOSED 2026-08-21: the secret-source dist (RE-HOMED
2026-08-09 to `tap-build-dependencies`; old repo archived, core's in-tree copy evicted,
doc-github-org-migration-plan records it) now rides the SAME lane — generalized with
`dist_name` + `project_dir` inputs and prefixed-tag parsing under the org tag grammar
`[<dist-name>-]vX.Y.Z` (req-cicd-release-artifacts in [spec-cicd-hardening.md](spec-cicd-hardening.md),
which owns the artifact-class model this lane serves); `aws-secrets-source-v0.2.0` is the first
prefixed-tag release. Original requirement text follows.

Plugins declare their own SBOMs, on the **declare-vs-decide** pattern the manifest
`[fips]` table established: the author's pipeline DECLARES, the system VERIFIES and
COMPOSES — it never re-derives blindly and never trusts blindly.

* **Declaration at release time.** The shared plugin release lane (plugin CI /
  `release-plugin.sh`) generates each plugin's SBOM from its own declared manifests
  (pyproject + lock), CycloneDX, published as a signed attestation against the release
  artifact — the same `attest-sbom` home and verify story as core (req-cicd-sbom-4).
  Identity keys on (package name, exact version): the boot-record entry key, so every
  layer joins on the same fact.
* **Composition, not re-scanning.** A flavored image build (req-cicd-sbom-9) VERIFIES
  each baked plugin's release-SBOM attestation; a running instance's boot record
  REFERENCES plugin SBOMs by digest/purl rather than restating them. Instance BOM =
  image-SBOM reference + per-plugin SBOM references + runtime deltas.
* **Derive-once at bake time.** A flavored image's true closure is the SINGLE bake-time
  resolution of core + plugins together (shared dependencies dedupe; version conflicts
  are the deps gate's job). The flavored artifact's SBOM therefore generates from that
  combined bake-time lock — one derivation. Plugin-declared release SBOMs serve the
  other two consumers: runtime (non-baked) installs, and the cross-check.
* **Declared-vs-derived cross-check.** What the bake derived MUST reconcile with what
  each baked plugin's author declared; a mismatch is a canary-guard red
  (req-cicd-sbom-7), never a silent preference for either side — disagreement between
  declaration and derivation is precisely the signal worth stopping for.
* **Trust rides the signing wave.** Plugin SBOM attestations inherit the org-rooted
  identity `req-tap-plugin-extdev-signing` lands
  (`tap_plugins/specs/spec-plugin-external-development.md`); no new trust machinery
  is invented here, and nothing blocks on it — GitHub-attested by CI is the interim
  posture; org-rooted plugin publisher identity hardening lands with
  `req-tap-plugin-extdev-signing`.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-10-1 | Identity matches or fails | Implemented | The SBOM's plugin component must match the expected dist name at the exact tag version; a mismatch (e.g. a shallow checkout building 0.0.0) fails. | |
| req-cicd-sbom-10-2 | Absent component fails | Implemented | A wheel SBOM without the plugin's own component fails the identity gate. | |
| req-cicd-sbom-10-3 | Wheel exemption is scoped | Implemented | Minimum-elements-lite exempts only the dependency graph; structural failures still fail closed. | |

### Standards Conformance Validation
----
RID: `req-cicd-sbom-11`

Status: `Implemented`

Before attesting, each generated SBOM MUST pass, fail-closed at the same gate point as
the canary guard:

* **Schema validation of BOTH emitted documents** against their declared spec
  versions — CycloneDX against the bom schema, SPDX against the SPDX JSON schema
  (vendored, pinned copies: a conformance gate that fetches its schemas from the
  network at publish time would be its own supply-chain hole).
* **Minimum-elements field checks** (CISA/NSA 2026 minimum elements): format name +
  version, SBOM/document version, generating tool name + version, generation
  timestamp/context, author, per-component **identifiers** (purl/CPE where they exist)
  and **hashes**, **dependency relationships** (the graph, not a flat list — the
  generation step of req-cicd-sbom-1/-6 MUST emit it; lockfiles carry the edges), and a
  **coverage/completeness statement** naming what the document does and does not cover
  (the known-unknowns discipline — SPDX-style NOASSERTION honesty in CycloneDX terms).
* **Signature mapping stated, not pretended:** the minimum-elements "author signature"
  is satisfied at the ATTESTATION layer (req-cicd-sbom-4's Sigstore-signed statement
  binding document to digest and workflow identity), not by an in-document signature.
  The conformance check verifies the document is *attestable* (hash-stable,
  schema-valid); the signature lives one layer up. If a consumer ever requires
  in-document signing, that is a named extension, not a silent gap.

Division of labor with req-cicd-sbom-7: canaries catch TAP-specific lies (a plausible
SBOM missing `tap` itself); conformance catches malformed valid-looking documents (a
structurally hollow SBOM full of unidentifiable components). Both are validation
surfaces → Validation Map rows at implementation.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-11-1 | Minimum elements pass and fail closed | Implemented | A conformant document passes; dropping serialNumber, timestamp, the dependency graph, the coverage statement, or a component's version each fails. | |
| req-cicd-sbom-11-2 | Identifier-coverage flood detected | Implemented | More than the tolerated handful of purl/CPE-less components fails with the offenders named. | |
| req-cicd-sbom-11-3 | Legacy tools array accepted | Implemented | CycloneDX's legacy tools-as-array serialization passes the tools check without error. | |

### Out-of-Band Detection Gate
----
RID: `req-cicd-sbom-12`

Status: `Implemented`

**Staging (2026-08-24):** the authoring-time Dockerfile guard is LIVE and fail-closed
(`scripts/sbom/oob_detect.py --dockerfile`, run as a unit test): every `COPY --from`
site must resolve to declared supplemental-manifest path(s) or carry an explicit
`# sbom-allow(<rid>): <reason>` annotation on the preceding comment line (Dockerfiles
have no trailing comments; the annotation binds to the next instruction only). The
publish-time unknowns budget (`--unknowns <image-ref> --fail`) is **FAIL-CLOSED since
2026-08-24**: an executable no apk package owns, no supplemental entry declares, and
no exclusion covers kills the publish before attestation. Flipped per its own staging
— dry run first (0 unknowns on both images, after two corrections the dry run itself
surfaced: apk ownership lives in the package's file INVENTORY, not its syft locations;
Wolfi's `usr/lib64` aliasing hides libffi from even `apk info --who-owns`), then one
green publish (run 32686098463) proving 0 on all four per-arch digests with the
js-vendor stage included, then the flip. Only FINDINGS were ever report-only;
operational failures always failed the job. The third piece, deterministic source-built
marking, is IMPLEMENTED: the built-from-source set is derived (never declared) from
`[tool.uv] no-binary-package` + the lock's sdist-only entries and marked in BOTH
serializations at generation (`tap:source-built` properties / SPDX comments), fail-closed
when a derived member is absent from the scan. First derived set: cryptography (forced,
the FIPS --no-binary discipline), psycopg-c + crontab (sdist-only upstream).

req-cicd-sbom-3's declaration duty MUST be **detected, never remembered**. Relying on an
author to recall the supplemental-entry rule while editing a Dockerfile is the opt-in
failure mode this spec exists to kill; the out-of-band inventory is deterministically
derivable, so derive it:

* **Authoring-time (Dockerfile-derived inventory).** Every out-of-band introduction
  site is statically enumerable from the Dockerfiles: `COPY --from=<external image>`
  (digest-pinned binary imports — `uv`/`uvx` today) and `COPY --from=<builder stage>`
  (self-built artifacts — `fips.so` today). A guard reconciles that derived set against
  the declared entries, both directions, and fails on any unmatched member (same
  harness family as the TAP-KNOWN-DUPE and workflow guards; ratchet-style, no
  baseline exceptions).

  **What this gate does and does not decide.** It reconciles **paths**: that every site
  lands a declared path, or carries an `sbom-allow`. It does not check that a declared
  **version** is true, and it must not be extended to — the version is no longer declared
  anywhere for it to check (req-cicd-sbom-3-4 derives it from the very pin this gate
  parses). Saying so here is the point: for four uv releases this gate was cited as the
  thing that kept the SBOM honest about versions, which it never was (tap#225). One
  parser serves both readers — `generate.parse_copy_sites` — so the set of sites this
  gate reconciles and the set generation derives from can never diverge.
* **Publish-time (image-level unknowns budget).** After generation, every executable
  and shared object in the scanned image MUST be accounted for: owned by an apk
  package, a member of the locked closure, or covered by a declared entry. The
  remainder — Syft's `unknowns` class, where `fips.so` surfaced in the groundwork —
  MUST be empty; any unclassified executable is a red publish. This is
  `req-fips-crypto-bom`'s fail-closed-on-unclassified discipline generalized from
  crypto providers to all executable content, and it is ecosystem-agnostic by
  construction: a hand-built binary in ANY language trips it on arrival.
* **Deterministic source-built marking (Python).** The set of Python packages built
  from source is derivable, not declarable: `[tool.uv] no-binary-package` plus the
  lock's sdist entries name them. The SBOM MUST mark those components as
  built-from-source (with the build context), derived from that configuration — never
  hand-maintained.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-12-1 | Undeclared COPY --from fails | Implemented | A `COPY --from` site whose destination path(s) are neither declared in the image's supplemental manifest nor covered by an `sbom-allow` annotation is a red. | The live authoring-time guard; both real Dockerfiles reconcile green against their real manifests. |
| req-cicd-sbom-12-2 | Annotations bind narrowly | Implemented | An `sbom-allow` annotation covers only the immediately following instruction — it never floats down the file to excuse later sites. | Prevents one blessed exception from silently blessing the next addition. |
| req-cicd-sbom-12-3 | Directory destinations compute per-file | Implemented | A dir-destination copy (`COPY --from=... /a /b /dest/`) is satisfied only when EVERY computed destination path is declared — one declared file cannot carry an undeclared sibling. | The uv/uvx two-binary site is the live example. |
| req-cicd-sbom-12-4 | Exemptions cite real rules | Implemented | An `sbom-allow` annotation exempts only when it names a requirement DEFINED in the spec tree AND carries a non-empty reason — a made-up id or a bare tag is a red, not a pass. | Codex/Grok finding on PR #115; a central exemption baseline/ratchet is the named future tightening if annotation count grows. |
| req-cicd-sbom-12-5 | Every spelling is seen or refused | Implemented | The parser handles case-insensitive instructions, reordered flags, line continuations, and JSON exec form; a COPY that mentions `--from` but resists parsing FAILS CLOSED rather than passing unexamined. | Codex bypass finding on PR #115: a guard that recognizes one spelling is a guard in name only. |
| req-cicd-sbom-12-6 | Source-built set is derived and marked | Implemented | The built-from-source members come from `[tool.uv] no-binary-package` plus sdist-only lock entries — never a hand-maintained list — and are marked in the generated SBOMs; a derived member absent from the scan fails generation. | The FIPS --no-binary builds (cryptography, psycopg-c) are the motivating members. |

### Ecosystem Coverage
----
RID: `req-cicd-sbom-13`

Status: `Implemented`

**JS gap CLOSED 2026-08-24, exactly on the doctrine's rails.** Identification pass
first: all five hand-vendored files hash-matched their npm release artifacts
byte-for-byte (htmx.org@2.0.4, echarts@6.0.0, cytoscape@3.30.4,
tabulator-tables@6.3.0 js + css) — no forks, no local patches, lossless migration.
The native tooling paid for itself on first contact, twice: `npm install` surfaced the
TRUE closure (echarts pulls `zrender` + `tslib` — dependencies the hand-vendoring
silently hid), and `npm audit` flagged the shipped echarts 6.0.0 with a known
moderate XSS (GHSA-fgmj-fm8m-jvvx) that nothing had been tracking — fixed by pinning
6.1.0 in the same change. Shipped shape: root `package.json` (exact pins) +
`package-lock.json`; `npm ci --ignore-scripts` in the digest-pinned `js-vendor` stage
(node + npm from Wolfi's apk repository on the pinned wolfi-base; originally node from
the ECR mirror); files staged under their historical app-relative static names into `/opt/tap-static-vendor` (outside the dev bind mount,
`STATICFILES_DIRS` guarded on existence so legacy images still boot); the lock rides
into the image and the scan catalogs it (`+javascript-lock-cataloger`); the four
libraries are publish canaries (req-cicd-sbom-7) so a dropped lockfile seam reds the
publish; the vendored bytes left git. Original doctrine text follows.

**Doctrine (George, 2026-08-20): adopt the ecosystem's own distribution system — never
roll our own.** Every package ecosystem present in a published artifact is consumed
through that ecosystem's native registry + lockfile + integrity format, and merged into
the SBOM approach at the LOCKFILE seam (the req-cicd-sbom-2 principle: derive from
declared, hash-verified manifests). The payoff is structural: the scanning, updating,
and advisory machinery of every ecosystem is built around its lockfile — Renovate,
Dependabot, Syft, and OSV all speak it natively — so adopting the standard buys the
SBOM slice, the update lane, and the vulnerability feed for free, while a parallel
hand-rolled distribution mechanism must rebuild all three and then maintain the
imitation forever. TAP's custom surface per ecosystem is deliberately confined to
**acquisition wiring** (fetch-verify-place inside the attested build) and the
fail-closed gates.

Per-ecosystem application:

* **Python** — covered: PyPI + `uv.lock`, hash-verified at acquisition, the -2
  derivation. The reference implementation of this requirement.
* **JavaScript — the NAMED EXISTING GAP, and the doctrine's first test.** Third-party
  JS currently ships as hand-vendored minified files (`tabulator.min.js`,
  `echarts.min.js`, `htmx.min.js`, `cytoscape.min.js` + tabulator css) — three of the
  five version-anonymous, invisible to every scanner and updater. The fix shape:
  `package.json` + `package-lock.json` in-repo as the declaration, acquisition by
  **`npm ci --ignore-scripts` in a digest-pinned node BUILDER stage** — the
  ecosystem's own acquisition tool, used the standard way, per this requirement's
  doctrine (a lock-parsing curl fetcher was considered and REJECTED as rolling our
  own npm client: npm versions the lock format, and `npm ci` is the reference
  implementation of its semantics). Same builder-stage boundary as `ossl-builder`
  and `deps-warm`: node never ships in the runtime image or touches the dev loop;
  `--ignore-scripts` closes the install-script vector, safe by construction since
  the stage extracts static assets and executes nothing. Only the dist files are
  copied out, to an image path outside the dev bind mount (`STATICFILES_DIRS`),
  bytes leaving git. Renovate maintains the lock natively; the lockfile in-repo feeds the
  dependency graph and Dependabot automatically; Syft's npm-lockfile cataloger joins
  the -1 derivation exactly as uv.lock does. First step regardless of shape: identify
  the four anonymous files' exact versions by hash-matching upstream release
  artifacts (any file matching NO release hash is an undeclared fork and must be
  surfaced, never silently re-pinned).
* **Rust (first-party, future)** — crates.io + `Cargo.lock`; `cargo-auditable`'s
  embedded metadata rides in the binary (the -2 exclusion applies only to third-party
  tool binaries whose closure is not ours; a first-party binary's closure is INCLUDED).
* **Go (future)** — module proxy + `go.sum`.
* **Hand-authored vendored-asset manifests (the Chromium `README.chromium` /
  `moz.yaml` pattern) are the LAST RESORT**, reserved for artifacts with no registry
  standard at all — which is the niche those conventions were actually built for
  (C/C++ vendoring). Each such manifest is a named debt carried in this requirement,
  never a pattern to extend. None exist today.

New ecosystems need no spec amendment to be caught: an unmanifested binary trips the
req-cicd-sbom-12 budget on arrival, and this requirement names the duty its author
then owes — adopt the ecosystem's standard, wire acquisition into the attested build,
select its lockfile cataloger into the derivation.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-13-1 | JS closure is canaried | Implemented | All four vendored browser libraries are required publish canaries for the web image — a package-lock seam that stops being cataloged reds the publish, never silently shrinks the SBOM. | |
| req-cicd-sbom-13-2 | Exact pins + integrity | Implemented | `package.json` declares exact versions (no ranges — the build is the artifact pin, updates are reviewed lock diffs) and every `package-lock.json` resolution carries an integrity hash. | The npm analog of uv.lock's hash-verified acquisition. |

### Consumer Verification Docs
----
RID: `req-cicd-sbom-14`

Status: `Proposed`

The canonical resolve-and-verify flow (req-cicd-sbom-5) MUST be carried verbatim in the
release/consumer documentation. Blocked on that surface existing — TAP has no
consumer-facing release docs home yet; when one lands (the Sam-facing adopter docs are
the likely vehicle), this requirement names the obligation that the flow lives there,
not only in this spec.

### Plugin SBOM Composition
----
RID: `req-cicd-sbom-15`

Status: `Proposed`

The composition half of req-cicd-sbom-10, split out so the declaration half's status can
be honest: a flavored ready-made image's SBOM derives ONCE from the bake-time combined
lock and MUST reconcile against each baked plugin's declared release SBOM
(declared-vs-derived disagreement is a canary red, req-cicd-sbom-7); a running
instance's boot record references plugin release SBOMs by digest/purl rather than
restating them — instance BOM = image-SBOM reference + per-plugin SBOM references +
runtime deltas. Rides the appliance arc with req-cicd-sbom-9; the fleet-wide plugin
release SBOMs (2026-08-20) are the ready inputs.

### Crypto Bill of Materials (CBOM) in the Image SBOM
----
RID: `req-cicd-sbom-16`

Status: `Proposed`

**What a CBOM is.** A CBOM is a bill of materials for cryptography: not "which packages are inside" but "which cryptographic
implementations, algorithms, protocols, certificates and key material are inside, and what was decided about each". There is no
separate CBOM format. CycloneDX 1.6 added the `cryptographic-asset` component type and a `cryptoProperties` block with four
`assetType` values: `algorithm`, `certificate`, `protocol`, `related-crypto-material` (read: `scripts/sbom/schemas/bom-1.6.schema.json`,
`definitions.cryptoProperties`). CycloneDX is also the Ecma standard ECMA-424: 1st edition = CycloneDX 1.6, 2nd edition = CycloneDX 1.7
(read: the Ecma-TC54/ECMA-424 repository README, <https://github.com/Ecma-TC54/ECMA-424>, which lists the 1st edition as v1.6 and the 2nd as
v1.7; the 2nd edition was published December 2025 per a web search of <https://tc54.org/cyclonedx/> and
<https://ecma-international.org/publications-and-standards/standards/ecma-424/>, search snippet, not read in full. The README did not
itself mention CBOM; that ECMA-424 covers cryptographic assets is the search snippet's wording and is NOT separately observed in the standard's text).

**The gap, measured.** `tap.crypto_bom` (`req-fips-crypto-bom`, Implemented) fingerprints native artifacts and gives each a disposition, as
a scan, a CI gate and a boot gate. It emits no CycloneDX (ran: `grep -rl cryptoProperties` over the tree matches only the vendored
`scripts/sbom/schemas/bom-1.6.schema.json`; the real tap-web:0.2.2 attestations, parsed, contain neither `cryptoProperties` nor a
`cryptographic-asset` component). What the attested SBOM already carries is one crypto fact: the self-built `openssl-fips-provider`
supplemental component with a derived `tap:fips-validation` property (read: both per-arch documents, 1 of 191 components). So the
published, signed, per-digest artifact says that a FIPS provider is present and its validation status, and does not say which of the
other binaries route through it, which are out of boundary, or what was decided. That last part lives only in a scan result.

**Why this is not a new pipeline.** Everything a CBOM document needs to be trustworthy already exists in this lane: a per-digest
derivation (`-1`, `-6`), out-of-band merging into the same document (`-3`), schema and minimum-elements validation (`-11`), a Sigstore
attestation bound to the digest with a release gate (`-4`), and a verify command. The missing piece is one more merge into the single
derivation, and a consumer that reads it.

#### Decision 1 - Scope: providers first; every other assetType named with its source

| assetType | In the first slice? | What it would need | Source that could supply it | Method |
| --- | :---: | --- | --- | --- |
| (provider) | Yes | A record of each crypto implementation found in an artifact and its disposition. CycloneDX has no provider assetType: the four values are algorithm, certificate, protocol, related-crypto-material, so a provider is a software component, not a cryptographic-asset | `tap.crypto_bom` findings (artifact path, provider, `Boundary`, rationale, rid) | read (schema enum; `tap/crypto_bom.py` `Finding`) |
| `algorithm` | No | Names of algorithms actually available and approved, with `primitive`, `certificationLevel`, `implementationPlatform` | NOT derivable from binary fingerprinting (the byte signatures name a provider, not its algorithms; `tap/crypto_providers.py` `SIGNATURES`). Candidate sources, each unverified for fitness: the validated module's own listing (`openssl list -digest-algorithms` etc. with the `fips` provider), the CMVP security policy for the certificate, or Python's `hashlib`/`cryptography` capability listing | read (signatures); ran: in the stat-card stack `openssl list -providers` shows `fips` 3.5.8 active and `-digest-algorithms` 74 lines, `-cipher-algorithms` 206, `-kdf-algorithms` 10, `-mac-algorithms` 6, `-signature-algorithms` 53 with `-provider fips -provider base` (line counts include aliases and headers, not a count of distinct algorithms). Whether the list is the approved subset is NOT OBSERVED |
| `protocol` | No | TLS/SSH versions and cipher suites a service is configured to accept | Declared configuration (openssl.cnf, the web tier's TLS settings, `libpq` `sslmode`), not binaries. Instance-level (what this deployment configures), so it belongs to the boot record before it belongs to the image | inferred |
| `certificate` | No | Subject, issuer, validity, signature algorithm | Deployed certificates exist at runtime (and `ca-certificates-bundle` is an apk, whose roots are data in a package). Instance-level; a collector, not the image derivation | inferred |
| `related-crypto-material` | No, deliberately | Keys, secrets, tokens: metadata only (type, state, `securedBy`) | The secret-source and `manage-secret` surface. The `value` field MUST NEVER be populated, and `crypto_provider` already refuses any key-material column (the no-key-material criterion of the `crypto_provider` model in the computing-core-tap spec) | read (computing-core spec); inferred (source) |

The artifact-versus-instance boundary of this spec's Philosophy applies unchanged: the image CBOM covers what every copy of this version
contains; configured protocols and live certificates are the instance's and ride the boot record or a collector.

#### Decision 2 - Mapping: a finding becomes properties on the owning component

A provider is not a cryptographic-asset, so the registry's vocabulary rides as `tap:`-namespaced properties on the component that owns the
artifact, the pattern this document already uses (`tap:fips-validation`, `tap:source-built`, `tap:path`) and the pattern Syft uses for repeated
facts (indexed names such as `syft:metadata:provides:0`, read in the real documents).

| Finding field | CycloneDX home | Note |
| --- | --- | --- |
| `provider` | `tap:crypto:<n>:provider` | the registry's name, verbatim (`openssl-system`, `rust-aws-lc-rs`, ...) |
| `boundary` | `tap:crypto:<n>:boundary` | exactly the five `Boundary` values; the disposition lives HERE and nowhere else in the document |
| `artifact` | `tap:crypto:<n>:artifact` | the path in the image, as `crypto_bom` reports it |
| `detail` / rationale | `tap:crypto:<n>:rationale` | the registry's reviewed sentence |
| `rid` | `tap:crypto:<n>:rid` | the requirement the disposition cites |

`<n>` is a per-component index. Owner resolution is the new work: the SBOM documents carry no file-to-package ownership (read: apk components
have `syft:location:0:path` = the apk database path, no per-file list, and no `evidence`), so the generator must derive the owner. For apk, the
file inventory the unknowns budget already reads (`scripts/sbom/oob_detect.py`, `req-cicd-sbom-12`); for files under the Python environment, the installed
distribution's RECORD (the derivation `req-fips-crypto-bom-waiver-ownership` proposes for waivers; the two SHOULD share one function); for
supplemental entries, the declared `tap:path`. **A finding whose owner cannot be resolved is never dropped**: it becomes a standalone component
of type `file` carrying the same properties, and the unowned count is reported in the coverage statement.

Rejected: (a) one `file` component per finding, always. It would add roughly 30 components to a 191-component document (ran: 30 findings in the
stat-card tap-web image) and pollute the package diff of `req-cicd-sbom-8`; kept only as the fallback above. (b) `cryptographic-asset` with
`assetType: algorithm` per provider. It asserts algorithms the scan did not observe, which is the plausible-but-wrong SBOM this spec exists to prevent.

`cryptographic-asset` components are reserved for Decision 1's later rows and are added only when a real source for them exists. Where they
are, the `dependencies[].provides` field (present in the vendored schema, read) links an owning component to the assets it implements.

#### Decision 3 - Placement: inside the single derivation, one document, one predicate

The CBOM is a **section of the existing CycloneDX document**, merged during generation like the supplemental components (`-3`) and the
source-built marks (`-12`), not a second scan and not a second attested file. `req-cicd-sbom-6` forbids a second independent scan of the same
facts; this is not one. Syft remains the sole component inventory, and `crypto_bom` observes a different fact (byte signatures in ELF files),
merged as annotations. Reasons for one document:

1. One attestation per digest and per predicate; the release gate (`-4`, tap#525) needs no new predicate and no new "missing attestation" state.
2. The consumer holds one hash-stable artifact answering "what is in it and what crypto does it use", and release diffs (`-8`) see one document.
3. The document is ~0.62 MB per arch (read: 615,427 and 624,316 bytes); a crypto section of tens of properties does not change that.

A separate CBOM document would be justified by: a CBOM-only consumer that rejects non-crypto components, or an independent release cadence. Neither
exists. If one appears, the answer is a **filtered view of this document** attested under a second predicate, never a rescan.

The scan input is the **exported filesystem of the verified per-arch digest**, using `scan()`'s explicit-roots interface (`req-fips-crypto-bom-3`), run by
first-party code in the generation job. It does not run the image's own copy of the scanner on itself. Binary roots map through the export prefix.

#### Decision 4 - Validation and attestation

* **Schema:** the document is already validated at generation. Read: `validate_schema` validates the CycloneDX document against the vendored **1.6** schema, and
  the real documents declare `specVersion: 1.7` (Syft 1.51.0). Both facts were read; whether 1.7 changed `cryptoProperties` relative to 1.6 is
  NOT OBSERVED (the 1.7 schema is not vendored). Before any `cryptographic-asset` is emitted, the vendored schema MUST match the emitted `specVersion`.
* **Fail-closed checks** (alongside `check_minimum_elements` and the canaries): every finding carries a disposition and a closed-vocabulary value; the sentinel
  of `req-fips-crypto-bom` holds in the document (the scan read binaries and saw `openssl-system` and the declared FIPS provider); the `tap:coverage` statement names
  providers as covered and algorithms, protocols, certificates and key material as not covered.
* **Attestation:** the existing `https://cyclonedx.org/bom` predicate, per arch digest, signed by the existing job. No new predicate type, because the document is the same document.
* **Ingestion verifies before it parses.** Ran, 2026-10-15: `gh attestation verify oci://ghcr.io/unified-systems-com/tap-web@sha256:d86ebb774dd2...0bc7 --owner
  unified-systems-com --predicate-type https://cyclonedx.org/bom --format json` exited 0 and returned one verified attestation. Its `statement.subject` digest was the
  requested digest, its `statement.predicateType` was `https://cyclonedx.org/bom`, and its signing certificate named
  `unified-systems-com/tap/.github/workflows/publish-images.yml@refs/heads/main`, a GitHub-hosted runner, at source commit `cbe3e700...`. The returned
  `statement.predicate` was byte-identical (canonical JSON) to the CycloneDX file another session had downloaded for that digest. So the parser MUST ingest the
  `statement.predicate` that verification returned, never a separately fetched file. What it proves: this document was signed by that workflow for that digest, recorded
  in the transparency log. What it does not: that the workflow's inputs were honest (the Residual named in `-4`), or that the cryptographic claims are right, only that TAP asserted them.

#### Decision 5 - Ingestion into the grid (the parser is shared with SBOM ingestion)

A CBOM parser is not a separate parser: it is the `tap:crypto:*` step of the one generic CycloneDX parser, because Decision 3 puts both in one document. What that
parser maps, with the computing_core vocabulary read from `specs/spec-computing-core-v0.md` in unified-systems-com/computing-core-tap:

| CycloneDX element | Grid result | Method |
| --- | --- | --- |
| the whole document | one SBOM node: full JSON, subject digest, attestation reference | George's stated intent; node type and owner are Open Decision B |
| `components[]` with purl type `apk`/`pypi`/`npm` | `package` keyed `(ecosystem = purl type, name, version)`; `purl`, `cpe`, `license` copied; `architecture` from the purl `arch` qualifier; `source_document: sbom` | read (spec); ran (101 apk, 71 pypi, 15 npm, 2 github, 1 generic, 1 without purl, in the real documents) |
| apk origin | `source_package` and `DERIVES_FROM_SOURCE_PACKAGE`, see below | ran |
| supplemental components (`tap:supplemental`) | `library` (and `SHIPS_LIBRARY` where a package ships it) | inferred from the `library` section of the computing-core-tap spec |
| `tap:crypto:<n>:*` | `crypto_provider` keyed `(scope, artifact, provider)` with `boundary` and `rationale`; `CARRIES_CRYPTO_PROVIDER` from the owning package/library | read (spec) |
| `metadata.component` (container, digest) | the image's host/OS context, `INSTALLS_PACKAGE` | Open Decision D |

**Convergence, not duplication.** `crypto_provider` nodes already exist (31 in the playground inventory bundle, per the support session's account; NOT OBSERVED by this
author). Parsed CBOM findings MUST produce the same identity `(scope, artifact, provider)` using the registry's own strings, so a parse updates those nodes and
creates none beside them. This is why Decision 2 keeps the artifact path and the provider name verbatim.

**The apk origin feeds `source_package` from the SBOM.** Verified on the real tap-web:0.2.2 documents (ran, both arm64 and amd64): `syft:metadata:originPackage` is present on
**101 of 101** apk components; the purl qualifier `upstream=` is present on **54 of 101**, exactly the components whose origin differs from their name (the other 47 are their own
origin, and the purl omits the qualifier). The property is therefore the complete source; the qualifier is a subset. The result is 69 distinct origins, 11 with more than one binary
package, which matches the apk-database observation recorded in the `source_package` section of the computing-core-tap spec (101 records, 69 sources, 11 multi-binary, 47 self-origin). In all 11 multi-binary
origins every member had one `version` string (ran). Neither source carries the origin's **version**; the node's key needs one, so it is taken from the member packages'
shared version (supported by the previous sentence and by the computing-core observation; a member with a differing version would be refused, not guessed). What this changes: nothing in the
types or edges; `source_package` and `DERIVES_FROM_SOURCE_PACKAGE` are unchanged. Only the feeder changes: the parser reads the SBOM instead of the apk database, and a join by source still never
needs a fallback branch because every package draws the edge.

#### Open decisions for the maintainer (not decided here)

* **A. Do the dependency links become edges?** The documents hold 458 `dependsOn` links on arm64 (356 apk to apk, 88 pypi to pypi, 14 npm to npm) and 420 on amd64 (318 apk) (ran), so the graph
  differs per architecture while `package` identity does not (`(ecosystem, name, version)`, architecture is not identity). Options: (1) none: the SBOM node's JSON keeps the graph and packages are
  nodes only (leaner, loses "what depends on this vulnerable library" in Gryphon); (2) a new package-to-package edge, needing a spec in the owning plugin and an arch discriminator or an accepted
  union across arches; (3) edges for pypi/npm only. Recommendation: (1) for the first slice, revisit when a question needs the graph; the document retains it, so nothing is lost.
* **B. Who owns the SBOM node and the parser?** (1) `computing_core`: the target types and edges are there, no new plugin; but that plugin is a vocabulary plugin and says "nothing in this plugin
  emits these types yet; a collector or bundle does" (read). (2) a new `*_core` plugin depending downward on `computing_core`: document, attestation reference and parser live together, vocabulary stays neutral; costs one more plugin. (3) `compliance_core`: the
  document is evidence, but it is not a finding. Recommendation: (2); fall back to (1) if the maintainer prefers fewer plugins.
* **C. Which assetTypes after providers, and from which source?** Decision 1 lists candidates; none is chosen. Recommendation: stop at providers until a consumer asks.
* **D. What is the host for an image?** `host` is keyed `(realm, stable_id)` and a container is a host with `kind: container`; an image digest is not a running container. Needs a ruling on a `realm` for an image
  digest before `INSTALLS_PACKAGE` is drawn.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-cicd-sbom-16-1 | One document | Proposed | The crypto section is merged into the primary CycloneDX document during the single derivation; no second CBOM document and no second predicate type exists. | Decision 3. |
| req-cicd-sbom-16-2 | Findings land on an owner | Proposed | Every `crypto_bom` finding for the scanned digest appears in the document as `tap:crypto:<n>:*` properties on its owning component; an unowned finding becomes a `file` component with the same properties and is counted in the coverage statement. None is dropped. | Decision 2. |
| req-cicd-sbom-16-3 | Closed disposition vocabulary | Proposed | `tap:crypto:<n>:boundary` is exactly one of the five `Boundary` values; a finding without one, or with another, fails generation. | A document may not launder an unclassified provider. |
| req-cicd-sbom-16-4 | Sentinel in the document | Proposed | Generation fails if the scan read no binaries, or did not see `openssl-system` and the declared FIPS provider. | The anti-fail-open sentinel of `req-fips-crypto-bom`, carried to the document. |
| req-cicd-sbom-16-5 | Coverage states the limits | Proposed | `tap:coverage` states that providers are covered and that algorithms, protocols, certificates and key material are not, until a later requirement adds them. | Known-unknowns discipline, `req-cicd-sbom-11`. |
| req-cicd-sbom-16-6 | Schema matches the emitted version | Proposed | The vendored CycloneDX schema used for validation has the same `specVersion` as the emitted document before any `cryptographic-asset` component is emitted. | Today a 1.7 document is validated against the 1.6 schema. |
| req-cicd-sbom-16-7 | Scan of the exported digest | Proposed | The scan reads the exported filesystem of the verified per-arch digest through explicit roots, in first-party code; the image never scans itself. | `req-fips-crypto-bom-3`; tap#507 token separation unchanged. |
| req-cicd-sbom-16-8 | No key material | Proposed | The document carries no `related-crypto-material` `value`, and no key, secret or token bytes under any `tap:crypto:*` property. | Mirrors the computing-core-tap `crypto_provider` no-key-material criterion. |
| req-cicd-sbom-16-9 | Verify before parse | Proposed | Ingestion parses only the `statement.predicate` returned by a successful `gh attestation verify --predicate-type https://cyclonedx.org/bom` for the document's subject digest, and records the digest and the verification outcome on the SBOM node. A failed or unobservable verification ingests nothing. | Three states as `-4`: verified, missing, not observable. |
| req-cicd-sbom-16-10 | One generic parser | Proposed | The CBOM mapping is a step of the same CycloneDX parser that maps packages, libraries and source packages; there is no second parser. | Decision 5. |
| req-cicd-sbom-16-11 | Provider identity converges | Proposed | A parsed finding keys on `(scope, artifact, provider)` with the registry's own strings, so it updates an existing `crypto_provider` node and never creates a second. | Decision 5. |
| req-cicd-sbom-16-12 | Source packages from the SBOM origin | Proposed | `source_package` nodes are derived from `syft:metadata:originPackage` (or `name` where equal), with the version taken from the members' shared version; a disagreeing member fails the parse. No type or edge changes. | Decision 5; observed 101/101, 69 origins, 11 multi-binary. |

## Non-Goals and Named Residuals

* **Runtime-added plugin SBOMs** — the boot record is the instance-level BOM for
  anything installed at boot rather than baked; out of scope here. The baked-plugin case
  is IN scope via req-cicd-sbom-9. Future seam (named, not built): the boot record
  references the image SBOM by digest rather than restating it — one fact, derived once,
  linked across layers.
* **Registry-side referrers copy** — deferred, see req-cicd-sbom-4.
* **Build-cache poisoning** — upstream of generation entirely; named and accepted at
  `req-cicd-supply-chain-provenance-1`. An SBOM inventories what was built; it cannot
  vouch that the build inputs were honest — that is provenance's job.
* *(SPDX emission was listed here as deferred; review moved it into day-one scope —
  req-cicd-sbom-6 now emits both formats from the single derivation.)*
