from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ["GITHUB_REF_NAME"]
TOKEN = os.environ["GITHUB_TOKEN"]
API = f"https://api.github.com/repos/{REPO}/contents"
SELF_PATH = ".github/scripts/one_time_patch_runtime_lock.py"
WORKFLOW_PATH = ".github/workflows/one-time-runtime-lock-patch.yml"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "aisearcharab-runtime-lock-patcher",
}


def request(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {detail}") from exc
    return json.loads(body) if body else {}


def content_url(path: str, *, with_ref: bool = False) -> str:
    encoded = urllib.parse.quote(path, safe="/")
    url = f"{API}/{encoded}"
    if with_ref:
        url += "?ref=" + urllib.parse.quote(BRANCH, safe="")
    return url


def read_file(path: str) -> tuple[str, str]:
    obj = request("GET", content_url(path, with_ref=True))
    raw = base64.b64decode(obj["content"])
    return raw.decode("utf-8"), obj["sha"]


def put_file(path: str, text: str, message: str, sha: str | None) -> None:
    payload = {
        "message": message,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    request("PUT", content_url(path), payload)


def delete_file(path: str, message: str) -> None:
    _, sha = read_file(path)
    request("DELETE", content_url(path), {"message": message, "sha": sha, "branch": BRANCH})


def require_once(text: str, needle: str, label: str) -> None:
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")


def patch_platform_api() -> None:
    path = ".github/workflows/platform-api.yml"
    text, sha = read_file(path)

    cache_old = "          cache-dependency-path: platform/apps/api/pyproject.toml\n"
    cache_new = (
        "          cache-dependency-path: |\n"
        "            platform/apps/api/pyproject.toml\n"
        "            platform/apps/api/requirements-runtime.lock\n"
    )
    require_once(text, cache_old, "platform cache input")
    text = text.replace(cache_old, cache_new, 1)

    start_marker = "      - name: Install API and test dependencies\n"
    end_marker = "      - name: Audit dependencies and generate VEX-aware CycloneDX SBOM\n"
    require_once(text, start_marker, "platform runtime block start")
    require_once(text, end_marker, "platform runtime block end")
    start = text.index(start_marker)
    end = text.index(end_marker)
    new_block = """      - name: Verify reviewed runtime lock integrity
        run: sha256sum -c requirements-runtime.lock.sha256

      - name: Install API and test dependencies
        run: |
          python -m pip install 'pip==26.1.2'
          python -m pip install -e '.[dev]'
          python -m pip install --require-hashes -r requirements-runtime.lock

      - name: Verify installed dependencies
        run: python -m pip check

      - name: Upload reviewed runtime lock evidence
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: phase3-1-runtime-lock
          path: platform/apps/api/requirements-runtime.lock
          if-no-files-found: error
          retention-days: 14

"""
    text = text[:start] + new_block + text[end:]

    audit_old = "          --lock /tmp/requirements-runtime.lock\n"
    audit_new = "          --lock requirements-runtime.lock\n"
    require_once(text, audit_old, "platform audit lock")
    text = text.replace(audit_old, audit_new, 1)

    if "pip-compile pyproject.toml" in text:
        raise RuntimeError("normal Platform API workflow still performs mutable runtime resolution")
    if "/tmp/requirements-runtime.lock" in text:
        raise RuntimeError("normal Platform API workflow still references the generated runtime lock")

    put_file(path, text, "ci: consume reviewed runtime lock in release gates", sha)


def patch_drift_workflow() -> None:
    path = ".github/workflows/dependency-drift-audit.yml"
    text, sha = read_file(path)

    watched = '      - "platform/apps/api/requirements-runtime.lock.sha256"\n'
    require_once(text, watched, "drift lock path")
    text = text.replace(
        watched,
        '      - "platform/apps/api/requirements-runtime.lock"\n' + watched,
        1,
    )

    dispatch = "  workflow_dispatch:\n"
    require_once(text, dispatch, "drift workflow_dispatch")
    text = text.replace(dispatch, '  schedule:\n    - cron: "0 6 * * 1"\n' + dispatch, 1)

    generate = "      - name: Generate current hashed runtime lock\n"
    require_once(text, generate, "drift generation step")
    text = text.replace(
        generate,
        "      - name: Verify committed reviewed lock integrity\n"
        "        run: sha256sum -c requirements-runtime.lock.sha256\n\n"
        "      - name: Generate current hashed runtime lock candidate\n",
        1,
    )

    start_marker = "      - name: Record generated lock digest\n"
    end_marker = "      - name: Audit generated lock before repinning\n"
    require_once(text, start_marker, "drift digest start")
    require_once(text, end_marker, "drift digest end")
    start = text.index(start_marker)
    end = text.index(end_marker)
    digest_block = """      - name: Record reviewed and candidate lock digests
        shell: bash
        run: |
          set -euo pipefail
          reviewed="$(awk '{print $1}' requirements-runtime.lock.sha256)"
          committed="$(sha256sum requirements-runtime.lock | awk '{print $1}')"
          candidate="$(sha256sum /tmp/requirements-runtime.lock | awk '{print $1}')"
          test -n "$reviewed"
          test "$committed" = "$reviewed"
          printf 'reviewed=%s\\ncommitted=%s\\ncandidate=%s\\n' "$reviewed" "$committed" "$candidate" | tee /tmp/runtime-lock-digest.txt

"""
    text = text[:start] + digest_block + text[end:]

    artifact_name = "          name: dependency-drift-review\n"
    require_once(text, artifact_name, "drift artifact name")
    text = text.replace(artifact_name, "          name: dependency-drift-review-${{ github.sha }}\n", 1)

    artifact_path = "          path: |\n            /tmp/requirements-runtime.lock\n"
    require_once(text, artifact_path, "drift artifact paths")
    text = text.replace(
        artifact_path,
        "          path: |\n"
        "            platform/apps/api/requirements-runtime.lock\n"
        "            /tmp/requirements-runtime.lock\n",
        1,
    )

    put_file(path, text, "ci: isolate mutable dependency resolution to drift audit", sha)


def write_docs() -> None:
    path = "docs/RUNTIME_DEPENDENCY_LOCK.md"
    docs = """# Runtime dependency lock policy

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
"""
    try:
        _, sha = read_file(path)
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
        sha = None
    put_file(path, docs, "docs: define runtime lock refresh and rollback policy", sha)


def verify_dockerfile() -> None:
    text, _ = read_file("platform/apps/api/Dockerfile")
    required = [
        "COPY pyproject.toml README.md requirements-runtime.lock requirements-runtime.lock.sha256 ./",
        "sha256sum -c requirements-runtime.lock.sha256",
        "python -m pip wheel --require-hashes --wheel-dir /wheels -r requirements-runtime.lock",
        "python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .",
    ]
    for needle in required:
        if needle not in text:
            raise RuntimeError(f"Dockerfile invariant missing: {needle}")
    if "pip-compile pyproject.toml" in text:
        raise RuntimeError("Dockerfile still performs mutable runtime resolution")


def main() -> None:
    lock_text, _ = read_file("platform/apps/api/requirements-runtime.lock")
    import hashlib

    digest = hashlib.sha256(lock_text.encode("utf-8")).hexdigest()
    expected = "b3200a67a9912364f17a6e5b2a07d780cedc6127f05e4da339791e9780035116"
    if digest != expected:
        raise RuntimeError(f"reviewed runtime lock digest mismatch: {digest}")

    verify_dockerfile()
    patch_platform_api()
    patch_drift_workflow()
    write_docs()

    # Remove all temporary write-capable bootstrap material from the branch.
    delete_file(WORKFLOW_PATH, "ci: remove one-time runtime lock patch workflow")
    delete_file(SELF_PATH, "ci: remove one-time runtime lock patch script")


if __name__ == "__main__":
    main()
