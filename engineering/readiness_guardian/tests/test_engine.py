import json

from readiness.engine import (
    Gate,
    Status,
    evaluate_invariants,
    import_json_payload,
    next_action_queue,
    production_decision,
    summarize,
)


def gate(id: str, status: Status, blocking: bool = True, verified: bool = False, category: str = "Security") -> Gate:
    return Gate(id=id, category=category, gate=id, status=status, blocking=blocking, evidence="evidence", verified=verified)


def test_fail_closed_non_pass_statuses_block_production():
    for status in (Status.FAIL, Status.BLOCKED, Status.PENDING, Status.UNKNOWN):
        assert production_decision([gate("G1", status)])["decision"] == "NO-GO"


def test_all_blocking_pass_allows_go():
    decision = production_decision([gate("A", Status.PASS), gate("B", Status.PASS), gate("C", Status.UNKNOWN, blocking=False)])
    assert decision["decision"] == "GO"


def test_empty_registry_is_no_go():
    assert production_decision([])["decision"] == "NO-GO"


def test_summary_metrics_are_computed_not_hardcoded():
    gates = [gate("A", Status.PASS, verified=True), gate("B", Status.PENDING), gate("C", Status.PASS, blocking=False, verified=False, category="Search/Trust")]
    summary = summarize(gates)
    assert summary["blocking_total"] == 2
    assert summary["blocking_pass"] == 1
    assert summary["blocking_gate_pass_rate"] == 0.5
    assert summary["verified_pass_rate"] == 1 / 3


def test_import_rejects_malformed_and_never_coerces_pass():
    payload = json.dumps({"gates": [
        {"id": "GOOD", "category": "Security", "gate": "Good", "status": "PASS", "blocking": True, "evidence": "ok"},
        {"id": "BAD", "category": "Security", "gate": "Bad", "status": "green", "blocking": True, "evidence": "bad"},
    ]})
    accepted, errors = import_json_payload(payload)
    assert [g.id for g in accepted] == ["GOOD"]
    assert accepted[0].verified is False
    assert errors


def test_action_queue_prioritizes_blocking_blocked_before_pending():
    gates = [gate("P", Status.PENDING), gate("B", Status.BLOCKED), gate("N", Status.UNKNOWN, blocking=False)]
    assert [g.id for g in next_action_queue(gates)] == ["B", "P", "N"]


def test_invariant_does_not_hold_when_dependency_missing_or_not_pass():
    gates = [gate("RATE-LIMIT", Status.PENDING), gate("PROD-ACT", Status.BLOCKED)]
    items = {i["id"]: i for i in evaluate_invariants(gates)}
    assert items["INV-RATE"]["holding"] is False
    assert items["INV-KEYS"]["holding"] is False
