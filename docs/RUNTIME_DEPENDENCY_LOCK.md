# Runtime dependency lock policy

## Authority

`platform/apps/api/pyproject.toml` declares the API's direct dependency constraints. The reviewed production install authority is `platform/apps/api/requirements-runtime.lock`; `requirements-runtime.lock.sha256` is its integrity and release identifier.

Normal CI and production container builds must not resolve the runtime dependency graph from the mutable package index. They verify the committed lock digest and install/build dependencies from the exact pinned versions and hashes in that lock.

## Release path

The production Docker build copies both the lock and checksum, verifies them with `sha256sum -c`, and builds dependency wheels with `pip --require-hashes`. The application wheel is built separately with pinned build tooling and `--no-build-isolation`. Runtime installation is from the locally built wheel directory with `--no-index`.

The Platform API gate audits the committed reviewed lock, generates its VEX-aware dependency evidence and CycloneDX SBOM, and uploads the committed lock as revision evidence. It does not run `pip-compile` in the normal release path.

## Refresh path

`.github/workflows/dependency-drift-audit.yml` is the only routine path that resolves a new candidate runtime graph from the mutable package index. It runs on demand, weekly, and for dependency-policy pull requests. The workflow:

1. verifies that the currently committed lock matches its reviewed checksum;
2. generates a candidate hashed lock with the pinned `pip-compile` toolchain;
3. records the reviewed, committed, and candidate digests;
4. performs the VEX-aware PyPI/OSV dependency audit;
5. generates and validates a CycloneDX SBOM;
6. publishes the reviewed lock, candidate lock, digest comparison, audit evidence, and SBOM as a revision-bound artifact.

A candidate artifact is evidence for review only. It never updates the production lock automatically.

## Promotion

To promote a candidate, review the dependency diff and audit/SBOM evidence, then commit the candidate as `requirements-runtime.lock` and update `requirements-runtime.lock.sha256` in the same pull request. The exact final pull-request head must pass the API, migration, container, security, and release-evidence gates before merge.

## Rollback

Rollback is a source-control operation: revert the lock and checksum together to a previously audited revision, then run the same release gates. Do not regenerate dependencies during rollback.

## Security boundary

This design prevents silent transitive-version drift between review and build. It does not make the build fully hermetic or guarantee package-index availability: exact artifacts are still fetched during the builder stage unless they are vendored or served from a controlled immutable mirror. Hash pinning also does not replace vulnerability review, provenance review, VEX handling, SBOM generation, or application tests.
