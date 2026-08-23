import json, subprocess, sys
from readiness.engine import Gate,Status,evaluate_invariants,export_json,import_json_payload,next_action_queue,production_decision,summarize

def gate(id:str,status:Status,blocking:bool=True,verified:bool=False,category:str="Security")->Gate:return Gate(id=id,category=category,gate=id,status=status,blocking=blocking,evidence="evidence",verified=verified)

def test_fail_closed_non_pass_statuses_block_production():
 for status in (Status.FAIL,Status.BLOCKED,Status.PENDING,Status.UNKNOWN):assert production_decision([gate("G1",status)])["decision"]=="NO-GO"

def test_arbitrary_verified_passes_cannot_bypass_mandatory_registry():assert production_decision([gate("A",Status.PASS,verified=True)])["decision"]=="NO-GO"

def test_full_mandatory_registry_requires_independent_authoritative_validation():
 from readiness.engine import MANDATORY_BLOCKING_GATE_IDS
 gates=[gate(gid,Status.PASS,verified=True) for gid in sorted(MANDATORY_BLOCKING_GATE_IDS)]
 assert production_decision(gates)["decision"]=="NO-GO"
 assert production_decision(gates,authoritative_release_validated=True)["decision"]=="GO"

def test_empty_registry_is_no_go():assert production_decision([])["decision"]=="NO-GO"

def test_summary_metrics_are_computed_not_hardcoded():
 gates=[gate("A",Status.PASS,verified=True),gate("B",Status.PENDING),gate("C",Status.PASS,blocking=False,category="Search/Trust")];summary=summarize(gates);assert summary["blocking_total"]==2 and summary["blocking_pass"]==1 and summary["blocking_gate_pass_rate"]==0.5 and summary["verified_pass_rate"]==1/3

def test_import_rejects_malformed_atomically():
 payload=json.dumps({"gates":[{"id":"GOOD","category":"Security","gate":"Good","status":"PASS","blocking":True,"evidence":"ok"},{"id":"BAD","category":"Security","gate":"Bad","status":"green","blocking":True,"evidence":"bad"}]});accepted,errors=import_json_payload(payload);assert accepted==[] and errors

def test_action_queue_prioritizes_blocking_blocked_before_pending():assert [g.id for g in next_action_queue([gate("P",Status.PENDING),gate("B",Status.BLOCKED),gate("N",Status.UNKNOWN,blocking=False)])]==["B","P","N"]

def test_invariant_missing_dependency_does_not_hold():
 items={i["id"]:i for i in evaluate_invariants([gate("RATE-LIMIT",Status.PENDING),gate("PROD-ACT",Status.BLOCKED)])};assert items["INV-RATE"]["holding"] is False and items["INV-KEYS"]["holding"] is False

def test_import_rejects_string_boolean_for_verified():
 payload=json.dumps({"gates":[{"id":"G1","category":"Security","gate":"Gate","status":"PASS","blocking":True,"evidence":"ok","verified":"false"}]});accepted,errors=import_json_payload(payload);assert accepted==[] and errors

def test_unverified_pass_still_blocks_production():assert production_decision([gate("G1",Status.PASS,verified=False)])["decision"]=="NO-GO"

def test_partial_mandatory_registry_cannot_go():
 decision=production_decision([gate("SEC-REG",Status.PASS,verified=True)]);assert decision["decision"]=="NO-GO" and "Mandatory gate registry" in decision["reason"]

def test_invariant_requires_verified_pass():
 items={i["id"]:i for i in evaluate_invariants([gate("RATE-LIMIT",Status.PASS,verified=False),gate("PROD-ACT",Status.PASS,verified=True)])};assert items["INV-RATE"]["holding"] is False

def test_export_json_materializes_generator_once():
 payload=json.loads(export_json((g for g in [gate("A",Status.PASS,verified=True)])));assert len(payload["gates"])==1 and payload["summary"]["blocking_total"]==1

def test_cli_malformed_snapshot_fails_closed(tmp_path):
 bad=tmp_path/"bad.json";bad.write_text('{"gates":[{"id":"x"}]}',encoding="utf-8");result=subprocess.run([sys.executable,"scripts/readiness_gate.py",str(bad)],capture_output=True,text=True);assert result.returncode==2 and "Decision: NO-GO" in result.stdout
