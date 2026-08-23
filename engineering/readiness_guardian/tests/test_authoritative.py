import json
import subprocess
import pytest
from readiness.authoritative import current_checkout_identity, validate_release_evidence_artifact


def _fake_repo(tmp_path):
    script = tmp_path / "platform" / "apps" / "api" / "scripts" / "release_evidence.py"
    script.parent.mkdir(parents=True)
    script.write_text("class ReleaseEvidence:\n    def __init__(self, **kwargs): self.__dict__.update(kwargs)\n    def validate(self): return None\n", encoding="utf-8")
    return tmp_path


def test_authoritative_artifact_must_match_expected_sha_and_ref(tmp_path):
    repo = _fake_repo(tmp_path)
    payload = json.dumps({"status": "PRODUCTION_READY", "source_ref": "refs/heads/main", "source_head_sha": "a" * 40, "tested_sha": "a" * 40, "blockers": []})
    with pytest.raises(ValueError, match="SHA mismatch"):
        validate_release_evidence_artifact(payload, repo, expected_sha="b" * 40, expected_source_ref="refs/heads/main")


def test_authoritative_artifact_must_match_expected_ref(tmp_path):
    repo = _fake_repo(tmp_path)
    payload = json.dumps({"status": "PRODUCTION_READY", "source_ref": "refs/heads/release-old", "source_head_sha": "a" * 40, "tested_sha": "a" * 40, "blockers": []})
    with pytest.raises(ValueError, match="ref mismatch"):
        validate_release_evidence_artifact(payload, repo, expected_sha="a" * 40, expected_source_ref="refs/heads/main")


def test_checkout_identity_is_grounded_in_git_not_github_ref(tmp_path, monkeypatch):
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "x.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/forged")
    sha, ref = current_checkout_identity(repo)
    assert ref == "refs/heads/main"
    assert sha == subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
