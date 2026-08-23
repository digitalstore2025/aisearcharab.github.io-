from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

try:
    from nicegui import run, ui
except ImportError as exc:
    raise SystemExit("Install dependencies with: pip install -r requirements.txt") from exc

from readiness.engine import Gate, evaluate_invariants, export_csv, export_json, import_json_payload, load_snapshot, next_action_queue, parse_gates, production_decision, summarize
from readiness.live_checks import run_live_checks

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = BASE_DIR / "data" / "snapshot.json"
MAX_UPLOAD_BYTES = 1024 * 1024
TEXT = {
    "ar": {"subtitle": "لوحة التحكم لجاهزية الإنتاج", "disclaimer": "أداة قرار وسجل أدلة فقط. لا تُفعّل الإنتاج بنفسها.", "gates": "بوابات الجاهزية", "actions": "الإجراءات التالية", "invariants": "الثوابت الأمنية", "live": "تشغيل فحص النطاق الحي", "import": "استيراد JSON", "json": "تصدير JSON", "csv": "تصدير CSV", "restore": "استعادة اللقطة الأصلية"},
    "en": {"subtitle": "Production Readiness Control Plane", "disclaimer": "Decision aid and evidence registry only. It never enables production by itself.", "gates": "Readiness Gates", "actions": "Next Actions", "invariants": "Security Invariants", "live": "Run live domain checks", "import": "Import JSON", "json": "Export JSON", "csv": "Export CSV", "restore": "Restore seed snapshot"},
}


class DashboardState:
    def __init__(self) -> None:
        self.locale = "ar"; self.restore()
    def restore(self) -> None:
        snapshot = load_snapshot(SNAPSHOT_PATH); self.metadata = snapshot.get("metadata", {}); self.gates = parse_gates(snapshot)


def pct(value: float) -> str: return f"{value * 100:.1f}%"

def table_row(gate: Gate) -> dict[str, str]:
    return {"id": gate.id, "category": gate.category, "gate": gate.gate, "status": gate.status.value, "blocking": "YES" if gate.blocking else "NO", "verified": "YES" if gate.verified else "NO", "next_action": gate.next_action}

ui.add_head_html("""<script>document.documentElement.dir='rtl';</script><style>body{background:#F8FAFC;color:#1E293B}.panel,.metric{background:#fff;border:1px solid #E2E8F0;border-radius:16px}</style>""")


@ui.page("/")
def dashboard() -> None:
    state = DashboardState()
    refs: dict[str, object] = {}

    def refresh_summary() -> None:
        summary = summarize(state.gates); decision = production_decision(state.gates)
        refs["decision"].set_text(decision["decision"]); refs["reason"].set_text(decision["reason"])
        refs["blocking"].set_text(pct(summary["blocking_gate_pass_rate"])); refs["verified"].set_text(pct(summary["verified_pass_rate"])); refs["trust"].set_text(pct(summary["trust_surface_completion"])); refs["blockers"].set_text(str(summary["blocking_not_pass"]))

    def refresh_table() -> None:
        query = (refs["query"].value or "").strip().lower(); status = refs["status"].value
        gates = [gate for gate in state.gates if (status == "ALL" or gate.status.value == status) and (not query or query in f"{gate.id} {gate.category} {gate.gate} {gate.evidence} {gate.next_action}".lower())]
        refs["table"].rows = [table_row(gate) for gate in gates]; refs["table"].update(); refs["evidence_select"].options = {gate.id: f"{gate.id} — {gate.gate}" for gate in state.gates}; refs["evidence_select"].update()

    def refresh_actions() -> None:
        container = refs["actions"]; container.clear()
        with container:
            for gate in next_action_queue(state.gates):
                with ui.row().classes("w-full items-start gap-2 border-b border-slate-100 py-2"):
                    ui.label(gate.status.value).classes("w-20 text-xs font-bold")
                    with ui.column().classes("gap-0"):
                        ui.label(f"{gate.id} — {gate.gate}").classes("text-sm font-semibold"); ui.label(gate.next_action or "Evidence/verification required.").classes("text-xs text-slate-500")

    def refresh_invariants() -> None:
        container = refs["invariants"]; container.clear()
        with container:
            for item in evaluate_invariants(state.gates):
                with ui.row().classes("w-full items-start justify-between gap-3 border-b border-slate-100 py-2"):
                    ui.label(item["statement"]).classes("text-sm"); ui.label(item["status"]).classes("text-xs font-bold")

    def refresh_all() -> None: refresh_summary(); refresh_table(); refresh_actions(); refresh_invariants()

    def set_locale(locale: str) -> None:
        state.locale = locale; text = TEXT[locale]
        for key, ref_key in (("subtitle", "subtitle"), ("disclaimer", "disclaimer"), ("gates", "gates_heading"), ("actions", "actions_heading"), ("invariants", "invariants_heading"), ("live", "live_button"), ("import", "import_label"), ("json", "json_label"), ("csv", "csv_label"), ("restore", "restore_label")): refs[ref_key].set_text(text[key])
        ui.run_javascript(f"document.documentElement.dir='{'rtl' if locale == 'ar' else 'ltr'}';")

    def show_evidence() -> None:
        gate_id = refs["evidence_select"].value; gate = next((item for item in state.gates if item.id == gate_id), None)
        if gate is None: ui.notify("Select a gate first.", type="warning"); return
        refs["dialog_title"].set_text(f"{gate.id} — {gate.gate}"); refs["dialog_body"].set_text(f"Status: {gate.status.value}\n\nEvidence: {gate.evidence}\n\nAcceptance: {gate.acceptance or 'Not specified.'}\n\nNext action: {gate.next_action or 'None.'}"); refs["dialog"].open()

    async def handle_upload(event) -> None:
        try:
            raw = event.content.read(MAX_UPLOAD_BYTES + 1)
            if len(raw) > MAX_UPLOAD_BYTES: ui.notify("Import rejected: payload exceeds 1 MiB.", type="negative"); return
            if isinstance(raw, bytes): raw = raw.decode("utf-8")
            gates, errors = import_json_payload(raw)
            if errors or not gates: ui.notify("Import rejected: " + "; ".join(errors[:3]), type="negative"); return
            state.gates = gates; state.metadata = {"source": "user-import", "provenance": "original metadata intentionally cleared"}; refresh_all(); ui.notify(f"Imported {len(gates)} gate(s).", type="positive")
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc: ui.notify(f"Import rejected: {exc}", type="negative")

    def download_text(filename: str, content: str) -> None:
        path = Path(tempfile.gettempdir()) / filename; path.write_text(content, encoding="utf-8"); ui.download(str(path))

    def restore_seed() -> None: state.restore(); refresh_all(); ui.notify("Seed snapshot restored.", type="positive")

    async def live_scan() -> None:
        refs["live_button"].disable(); refs["live_status"].set_text("Running network checks…")
        try:
            live = await run.io_bound(run_live_checks, "https://aisearch.study"); retained = [gate for gate in state.gates if not gate.id.startswith(("LIVE-", "TRUST-"))]; state.gates = retained + live; refresh_all(); refs["live_status"].set_text(f"Live scan complete: {len(live)} records.")
        except Exception as exc: refs["live_status"].set_text(f"Live scan failed safely: {exc}")
        finally: refs["live_button"].enable()

    with ui.column().classes("mx-auto w-full max-w-[1500px] gap-4 p-4 md:p-6"):
        with ui.row().classes("panel w-full items-center justify-between p-5"):
            with ui.column().classes("gap-0"):
                ui.label("aisearch.study").classes("text-xl font-extrabold"); refs["subtitle"] = ui.label(TEXT["ar"]["subtitle"]).classes("text-sm text-slate-500"); ui.label("تعلّم بذكاء").classes("text-xs font-semibold text-blue-600")
            ui.toggle({"ar": "AR", "en": "EN"}, value="ar", on_change=lambda e: set_locale(e.value)).props("dense")
        refs["disclaimer"] = ui.label(TEXT["ar"]["disclaimer"]).classes("w-full rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm")
        with ui.card().classes("w-full border border-red-200 bg-red-50 shadow-none"):
            refs["decision"] = ui.label("NO-GO").classes("text-3xl font-black text-red-700"); refs["reason"] = ui.label("").classes("text-sm"); ui.label("GENERATED_ANSWERS_ENABLED=false").classes("font-mono text-xs")
        with ui.grid(columns=4).classes("w-full gap-3 max-md:grid-cols-2 max-sm:grid-cols-1"):
            for title, key in (("Blocking Gate Pass Rate", "blocking"), ("Verified Pass Rate", "verified"), ("Trust Surface Completion", "trust"), ("Blocking Gates Not Pass", "blockers")):
                with ui.card().classes("metric shadow-none"): ui.label(title).classes("text-xs text-slate-500"); refs[key] = ui.label("0").classes("text-3xl font-extrabold")
        with ui.card().classes("panel w-full shadow-none"):
            with ui.row().classes("w-full items-center justify-between"):
                refs["live_status"] = ui.label("Live checks are opt-in and fail closed.").classes("text-xs text-slate-500"); refs["live_button"] = ui.button(TEXT["ar"]["live"], on_click=live_scan).props("outline")
        with ui.card().classes("panel w-full shadow-none"):
            refs["gates_heading"] = ui.label(TEXT["ar"]["gates"]).classes("text-lg font-bold")
            with ui.row().classes("w-full gap-3"):
                refs["query"] = ui.input("Search").props("dense outlined clearable").classes("flex-1"); refs["status"] = ui.select(["ALL", "PASS", "FAIL", "PENDING", "BLOCKED", "UNKNOWN"], value="ALL", label="Status").props("dense outlined")
            refs["query"].on_value_change(lambda _: refresh_table()); refs["status"].on_value_change(lambda _: refresh_table())
            columns = [{"name": "id", "label": "ID", "field": "id", "align": "left"}, {"name": "category", "label": "Category", "field": "category", "align": "left"}, {"name": "gate", "label": "Gate", "field": "gate", "align": "left"}, {"name": "status", "label": "Status", "field": "status", "align": "left"}, {"name": "blocking", "label": "Blocking", "field": "blocking", "align": "left"}, {"name": "verified", "label": "Verified", "field": "verified", "align": "left"}, {"name": "next_action", "label": "Next action", "field": "next_action", "align": "left"}]
            refs["table"] = ui.table(columns=columns, rows=[], row_key="id", pagination=15).classes("w-full").props("flat bordered dense wrap-cells")
            with ui.row().classes("w-full items-end gap-2"):
                refs["evidence_select"] = ui.select({}, label="Evidence record").classes("flex-1").props("outlined dense"); ui.button("View evidence", on_click=show_evidence).props("outline")
        with ui.grid(columns=2).classes("w-full gap-3 max-lg:grid-cols-1"):
            with ui.card().classes("panel shadow-none"): refs["actions_heading"] = ui.label(TEXT["ar"]["actions"]).classes("text-lg font-bold"); refs["actions"] = ui.column().classes("w-full gap-0")
            with ui.card().classes("panel shadow-none"): refs["invariants_heading"] = ui.label(TEXT["ar"]["invariants"]).classes("text-lg font-bold"); refs["invariants"] = ui.column().classes("w-full gap-0")
        with ui.card().classes("panel w-full shadow-none"):
            with ui.row().classes("items-center gap-2"):
                ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.json max-files=1 max-file-size=1048576"); refs["import_label"] = ui.label(TEXT["ar"]["import"]).classes("text-xs text-slate-500")
                json_button = ui.button(on_click=lambda: download_text("aisearch-readiness.json", export_json(state.gates, state.metadata))).props("outline")
                with json_button: refs["json_label"] = ui.label(TEXT["ar"]["json"])
                csv_button = ui.button(on_click=lambda: download_text("aisearch-readiness.csv", export_csv(state.gates))).props("outline")
                with csv_button: refs["csv_label"] = ui.label(TEXT["ar"]["csv"])
                restore_button = ui.button(on_click=restore_seed).props("flat")
                with restore_button: refs["restore_label"] = ui.label(TEXT["ar"]["restore"])
    with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[95vw]"):
        refs["dialog"] = dialog; refs["dialog_title"] = ui.label("").classes("text-lg font-bold"); refs["dialog_body"] = ui.label("").classes("whitespace-pre-wrap text-sm"); ui.button("Close", on_click=dialog.close).props("flat")
    refresh_all()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="AISearch Study — Readiness Guardian", host=os.getenv("READINESS_BIND_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8080")), reload=False, show=False)
