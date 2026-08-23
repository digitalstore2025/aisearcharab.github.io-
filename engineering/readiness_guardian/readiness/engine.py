from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
import csv, io, json

class Status(str, Enum):
    PASS="PASS"; FAIL="FAIL"; BLOCKED="BLOCKED"; PENDING="PENDING"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class Gate:
    id:str; category:str; gate:str; status:Status; blocking:bool; evidence:str; source:str=""; acceptance:str=""; next_action:str=""; verified:bool=False; trust_surface:bool=False

REQUIRED_FIELDS=("id","category","gate","status","blocking","evidence")
MANDATORY_BLOCKING_GATE_IDS=frozenset({"SEC-REG","SEC-DIFF","SEARCH-REG","OPENAPI","RATE-LIMIT","OBSERVABILITY","HC-FINDINGS","SECRET-MGR","PROD-ACT","RELEASE-EVIDENCE"})
SECURITY_INVARIANTS={
 "INV-RATE":{"statement":"No AI generation without verified distributed/persistent per-user rate limiting.","depends_on":["RATE-LIMIT","PROD-ACT"]},
 "INV-KEYS":{"statement":"No real API keys in frontend, Git, tests, logs, or documentation.","depends_on":["SECRET-MGR"]},
 "INV-CITATIONS":{"statement":"Unknown citations fail closed.","depends_on":["SEC-REG","OPENAPI"]},
 "INV-OUTPUTS":{"statement":"Malformed model/provider outputs fail closed.","depends_on":["SEC-DIFF","SEC-REG"]},
 "INV-FINDINGS":{"statement":"No production activation with unresolved High/Critical findings.","depends_on":["HC-FINDINGS","PROD-ACT"]},
}

def load_snapshot(path:str|Path)->dict[str,Any]:
 data=json.loads(Path(path).read_text(encoding="utf-8"))
 if not isinstance(data,dict) or not isinstance(data.get("gates"),list): raise ValueError("Snapshot must be an object containing a 'gates' array.")
 return data

def _optional_bool(raw:dict[str,Any],field:str,default:bool=False)->bool:
 if field not in raw:return default
 value=raw[field]
 if not isinstance(value,bool):raise ValueError(f"'{field}' must be a boolean when provided.")
 return value

def _optional_bool_alias(raw:dict[str,Any],primary:str,alias:str,default:bool=False)->bool:
 if primary in raw and alias in raw:raise ValueError(f"Provide only one of '{primary}' or '{alias}'.")
 if primary in raw:return _optional_bool(raw,primary,default)
 if alias in raw:return _optional_bool(raw,alias,default)
 return default

def _normalize_gate(raw:dict[str,Any])->Gate:
 missing=[f for f in REQUIRED_FIELDS if f not in raw]
 if missing:raise ValueError(f"Missing required field(s): {', '.join(missing)}")
 try:status=Status(str(raw["status"]).upper())
 except ValueError as exc:raise ValueError(f"Invalid status: {raw.get('status')!r}") from exc
 if not isinstance(raw["blocking"],bool):raise ValueError("'blocking' must be a boolean.")
 for field in ("id","category","gate","evidence"):
  if not isinstance(raw[field],str) or not raw[field].strip():raise ValueError(f"'{field}' must be a non-empty string.")
 return Gate(id=raw["id"].strip(),category=raw["category"].strip(),gate=raw["gate"].strip(),status=status,blocking=raw["blocking"],evidence=raw["evidence"].strip(),source=str(raw.get("source","")).strip(),acceptance=str(raw.get("acceptance",raw.get("acceptanceCriteria",""))).strip(),next_action=str(raw.get("next_action",raw.get("nextAction",""))).strip(),verified=_optional_bool(raw,"verified",False),trust_surface=_optional_bool_alias(raw,"trust_surface","trustSurface",False))

def parse_gates(snapshot:dict[str,Any])->list[Gate]:
 seen=set();gates=[]
 for index,raw in enumerate(snapshot["gates"]):
  if not isinstance(raw,dict):raise ValueError(f"Gate #{index} is not an object.")
  gate=_normalize_gate(raw)
  if gate.id in seen:raise ValueError(f"Duplicate gate id: {gate.id}")
  seen.add(gate.id);gates.append(gate)
 return gates

def import_json_payload(text:str)->tuple[list[Gate],list[str]]:
 try:payload=json.loads(text)
 except json.JSONDecodeError as exc:return [],[f"Invalid JSON: {exc.msg}"]
 if isinstance(payload,list):raw_gates=payload
 elif isinstance(payload,dict) and isinstance(payload.get("gates"),list):raw_gates=payload["gates"]
 else:return [],["Expected a gate array or an object with a 'gates' array."]
 accepted=[];errors=[];seen=set()
 for index,raw in enumerate(raw_gates):
  try:
   if not isinstance(raw,dict):raise ValueError("entry is not an object")
   gate=_normalize_gate(raw)
   if gate.id in seen:raise ValueError(f"duplicate gate id: {gate.id}")
   seen.add(gate.id);accepted.append(gate)
  except ValueError as exc:errors.append(f"#{index}: {exc}")
 if errors:return [],errors
 by_id={g.id:g for g in accepted};missing=sorted(MANDATORY_BLOCKING_GATE_IDS-by_id.keys())
 if missing:return [],["Missing mandatory blocking gate(s): "+", ".join(missing)]
 downgraded=sorted(gid for gid in MANDATORY_BLOCKING_GATE_IDS if not by_id[gid].blocking)
 if downgraded:return [],["Mandatory gate(s) cannot be non-blocking: "+", ".join(downgraded)]
 return accepted,[]

def is_pass(gate:Gate)->bool:return gate.status==Status.PASS

def is_verified_pass(gate:Gate)->bool:return is_pass(gate) and gate.verified and bool(gate.evidence.strip())

def production_decision(gates:Iterable[Gate])->dict[str,Any]:
 gates=list(gates);by_id={g.id:g for g in gates};mandatory_present=MANDATORY_BLOCKING_GATE_IDS.intersection(by_id)
 if mandatory_present:
  missing=sorted(MANDATORY_BLOCKING_GATE_IDS-by_id.keys());downgraded=sorted(gid for gid in MANDATORY_BLOCKING_GATE_IDS if gid in by_id and not by_id[gid].blocking)
  if missing or downgraded:
   details=[]
   if missing:details.append("missing="+",".join(missing))
   if downgraded:details.append("non_blocking="+",".join(downgraded))
   return {"decision":"NO-GO","reason":"Mandatory gate registry is incomplete or downgraded: "+"; ".join(details),"blockers":[by_id[g] for g in downgraded]}
 blocking=[g for g in gates if g.blocking];blockers=[g for g in blocking if not is_verified_pass(g)]
 if not blocking:return {"decision":"NO-GO","reason":"No blocking gates are registered; absence of controls is not readiness.","blockers":[]}
 if blockers:return {"decision":"NO-GO","reason":f"{len(blockers)} blocking gate(s) are not verified PASS.","blockers":blockers}
 return {"decision":"GO","reason":"Every blocking gate is verified PASS, including authoritative release evidence when using the project registry.","blockers":[]}

def summarize(gates:Iterable[Gate])->dict[str,Any]:
 gates=list(gates);blocking=[g for g in gates if g.blocking];blocking_pass=[g for g in blocking if is_pass(g)];verified=[g for g in gates if is_verified_pass(g)];trust=[g for g in gates if g.trust_surface or g.category=="Search/Trust"];trust_pass=[g for g in trust if is_pass(g)];decision=production_decision(gates)
 ratio=lambda n,d:0.0 if d==0 else n/d
 return {"blocking_gate_pass_rate":ratio(len(blocking_pass),len(blocking)),"verified_pass_rate":ratio(len(verified),len(gates)),"trust_surface_completion":ratio(len(trust_pass),len(trust)),"blocking_total":len(blocking),"blocking_pass":len(blocking_pass),"blocking_not_pass":len(blocking)-len(blocking_pass),"production_go":decision["decision"]=="GO","decision":decision["decision"],"decision_reason":decision["reason"]}

_STATUS_WEIGHT={Status.FAIL:0,Status.BLOCKED:1,Status.UNKNOWN:2,Status.PENDING:3,Status.PASS:4}
def next_action_queue(gates:Iterable[Gate])->list[Gate]:return sorted((g for g in gates if not is_pass(g)),key=lambda g:(0 if g.blocking else 1,_STATUS_WEIGHT[g.status],g.id))

def evaluate_invariants(gates:Iterable[Gate])->list[dict[str,Any]]:
 by_id={g.id:g for g in gates};results=[]
 for invariant_id,cfg in SECURITY_INVARIANTS.items():
  dependencies=[by_id.get(gid) for gid in cfg["depends_on"]];missing=[gid for gid,gate in zip(cfg["depends_on"],dependencies) if gate is None];blockers=[gate for gate in dependencies if gate is not None and not is_verified_pass(gate)];holding=not missing and not blockers
  results.append({"id":invariant_id,"statement":cfg["statement"],"holding":holding,"status":"PASS" if holding else "NOT-HOLDING","missing":missing,"blocked_by":[f"{g.id} ({g.status.value})" for g in blockers]})
 return results

def gate_to_dict(gate:Gate)->dict[str,Any]:
 data=asdict(gate);data["status"]=gate.status.value;return data

def export_json(gates:Iterable[Gate],metadata:dict[str,Any]|None=None)->str:
 gates=list(gates);return json.dumps({"metadata":metadata or {},"gates":[gate_to_dict(g) for g in gates],"summary":summarize(gates)},indent=2,ensure_ascii=False)

def export_csv(gates:Iterable[Gate])->str:
 fields=["id","category","gate","status","blocking","verified","trust_surface","evidence","source","acceptance","next_action"];stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
 for gate in gates:writer.writerow(gate_to_dict(gate))
 return stream.getvalue()
