import json
import pytest
from readiness.authoritative import validate_release_evidence_artifact


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
