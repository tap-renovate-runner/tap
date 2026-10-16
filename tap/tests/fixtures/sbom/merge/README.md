# merge fixtures (tests for scripts/sbom/merge_enrich.py, req-cicd-sbom-18 and -20)

Real data, trimmed with `jq`. Nothing here is invented except `meta.json` and the base SBOM's identity fields.

- `sbom.cdx.json` - the two-component probe SBOM (log4j-core 2.14.1, PyJWT 2.13.0) given a serialNumber, `version` 1
  and a `tap:completeness` property, i.e. a revision-1 document.
- `grype.json` - Grype v0.120.1 NATIVE JSON for that probe, cut to the two matches `GHSA-jfh8-c2jp-5v3q`
  (aliases CVE-2021-44228; on the KEV list) and `GHSA-p6xc-xr62-6r2g` (CVE-2021-45105; not on it). Descriptions,
  advisories, match details and artifact locations were deleted.
- `kev.json` - CISA's `known_exploited_vulnerabilities.json` (catalogVersion 2026.10.14) cut to the entries for
  CVE-2021-44228 and CVE-2022-22965.
- `cve.json` - CVE Program JSON 5 records for CVE-2021-44228 and CVE-2021-45105 fetched from
  `https://cveawg.mitre.org/api/cve/<id>` on 2026-10-16, keeping `cveMetadata`, the CNA metrics and problem types, and
  the CISA-ADP container's metrics.
- `meta.json` - a scan time, an attestation digest and fetch times chosen for the tests.
