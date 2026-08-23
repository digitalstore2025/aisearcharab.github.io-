from __future__ import annotations

import os
import tempfile
from pathlib import Path

try:
    from nicegui import ui, run
except ImportError as exc:
    raise SystemExit("NiceGUI is not installed. Run: pip install -r requirements.txt") from exc

from readiness.engine import (
    Gate,
    Status,
    evaluate_invariants,
    export_csv,
    export_json,
    import_json_payload,
    load_snapshot,
    next_action_queue,
    parse_gates,
    production_decision,
    summarize,
)
from readiness.live_checks import run_live_checks


BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = BASE_DIR / "data" / "snapshot.json"

TEXT = {
    "en": {
        "subtitle": "Production Readiness Control Plane",
        "disclaimer": "Decision aid and evidence registry only. This dashboard never enables production by itself.",
        "gates": "Readiness Gates",
        "actions": "Next Actions",
        "invariants": "Security Invariants",
        "trust": "Trust & Domain",
        "run_live": "Run live domain checks",
        "import": "Import JSON",
        "export_json": "Export JSON",
        "export_csv": "Export CSV",
        "restore": "Restore seed snapshot",
    },
    "ar": {
        "subtitle": "لوحة التحكم لجاهزية الإنتاج",
        "disclaimer": "أداة قرار وسجل أدلة فقط. هذه اللوحة لا تُفعّل الإنتاج بنفسها.",
        "gates": "بوابات الجاهزية",
        "actions": "الإجراءات التالية",
        "invariants": "الثوابت الأمنية",
        "trust": "الثقة والنطاق",
        "run_live": "تشغيل فحص النطاق الحي",
        "import": "استيراد JSON",
        "export_json": "تصدير JSON",
        "export_csv": "تصدير CSV",
        "restore": "استعادة اللقطة الأصلية",
    },
}


class DashboardState:
    def __init__(self) -> None:
        snapshot = load_snapshot(SNAPSHOT_PATH)
        self.metadata = snapshot.get("metadata", {})
        self.gates = parse_gates(snapshot)
        self.locale = "ar"


state = DashboardState()
refs: dict[str, object] = {}


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def gate_dict(g: Gate) -> dict:
    return {
        "id": g.id,
        "category": g.category,
        "gate": g.gate,
        "status": g.status.value,
        "blocking": "YES" if g.blocking else "NO",
        "verified": "YES" if g.verified else "NO",
        "evidence": g.evidence,
        "acceptance": g.acceptance,
        "next_action": g.next_action,
    }


def status_classes(status: Status | str) -> str:
    value = status.value if isinstance(status, Status) else str(status)
    return {
        "PASS": "bg-green-50 text-green-700 border-green-200",
        "FAIL": "bg-red-50 text-red-700 border-red-200",
        "BLOCKED": "bg-red-50 text-red-700 border-red-200",
        "UNKNOWN": "bg-amber-50 text-amber-700 border-amber-200",
        "PENDING": "bg-slate-50 text-slate-700 border-slate-200",
    }.get(value, "bg-slate-50 text-slate-700 border-slate-200")


def refresh_summary() -> None:
    summary = summarize(state.gates)
    decision = production_decision(state.gates)
    refs["decision"].set_text(decision["decision"])
    refs["decision_reason"].set_text(decision["reason"])
    refs["kpi_blocking"].set_text(pct(summary["blocking_gate_pass_rate"]))
    refs["kpi_verified"].set_text(pct(summary["verified_pass_rate"]))
    refs["kpi_trust"].set_text(pct(summary["trust_surface_completion"]))
    refs["kpi_blockers"].set_text(str(summary["blocking_not_pass"]))
    decision_card = refs["decision_card"]
    if decision["decision"] == "GO":
        decision_card.classes(remove="border-red-200 bg-red-50", add="border-green-200 bg-green-50")
        refs["decision"].classes(remove="text-red-700", add="text-green-700")
    else:
        decision_card.classes(remove="border-green-200 bg-green-50", add="border-red-200 bg-red-50")
        refs["decision"].classes(remove="text-green-700", add="text-red-700")


def refresh_table() -> None:
    query = (refs["filter_query"].value or "").strip().lower()
    status = refs["filter_status"].value
    category = refs["filter_category"].value
    blocking = refs["filter_blocking"].value
    filtered = []
    for gate in state.gates:
        if status != "ALL" and gate.status.value != status:
            continue
        if category != "ALL" and gate.category != category:
            continue
        if blocking != "ALL" and gate.blocking != (blocking == "YES"):
            continue
        haystack = f"{gate.id} {gate.category} {gate.gate} {gate.evidence} {gate.next_action}".lower()
        if query and query not in haystack:
            continue
        filtered.append(gate)
    refs["gate_table"].rows = [gate_dict(g) for g in filtered]
    refs["gate_table"].update()
    refs["evidence_select"].options = {g.id: f"{g.id} — {g.gate}" for g in state.gates}
    refs["evidence_select"].update()


def refresh_actions() -> None:
    container = refs["actions_container"]
    container.clear()
    with container:
        for idx, gate in enumerate(next_action_queue(state.gates), start=1):
            with ui.row().classes("w-full items-start gap-3 border-b border-slate-100 py-3 last:border-0"):
                ui.label(str(idx)).classes("grid h-6 w-6 place-items-center rounded-full bg-slate-900 text-xs text-white")
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(gate.id).classes("font-mono text-xs font-bold text-slate-800")
                        ui.label(gate.status.value).classes(f"rounded-full border px-2 py-0.5 text-[10px] font-bold {status_classes(gate.status)}")
                        if gate.blocking:
                            ui.label("BLOCKING").classes("rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700")
                    ui.label(gate.next_action or "Evidence/verification required.").classes("text-sm text-slate-600")


def refresh_invariants() -> None:
    container = refs["invariants_container"]
    container.clear()
    with container:
        for item in evaluate_invariants(state.gates):
            with ui.row().classes("w-full items-start justify-between gap-4 border-b border-slate-100 py-3 last:border-0"):
                with ui.column().classes("gap-1"):
                    ui.label(item["statement"]).classes("text-sm font-semibold text-slate-800")
                    details = []
                    if item["blocked_by"]:
                        details.append("Blocked by: " + ", ".join(item["blocked_by"]))
                    if item["missing"]:
                        details.append("Missing: " + ", ".join(item["missing"]))
                    ui.label(" · ".join(details) or "All dependent gates PASS.").classes("text-xs text-slate-500")
                ui.label(item["status"]).classes("rounded-full border px-2 py-1 text-[10px] font-bold " + ("border-green-200 bg-green-50 text-green-700" if item["holding"] else "border-red-200 bg-red-50 text-red-700"))


def refresh_all() -> None:
    refs["filter_category"].options = ["ALL"] + sorted({g.category for g in state.gates})
    refs["filter_category"].update()
    refresh_summary()
    refresh_table()
    refresh_actions()
    refresh_invariants()


def set_locale(locale: str) -> None:
    state.locale = locale
    text = TEXT[locale]
    refs["subtitle"].set_text(text["subtitle"])
    refs["disclaimer"].set_text(text["disclaimer"])
    refs["gates_heading"].set_text(text["gates"])
    refs["actions_heading"].set_text(text["actions"])
    refs["invariants_heading"].set_text(text["invariants"])
    refs["live_button"].set_text(text["run_live"])
    refs["import_label"].set_text(text["import"])
    refs["export_json_label"].set_text(text["export_json"])
    refs["export_csv_label"].set_text(text["export_csv"])
    refs["restore_label"].set_text(text["restore"])
    ui.run_javascript(f"document.documentElement.dir='{'rtl' if locale == 'ar' else 'ltr'}';")


def show_evidence() -> None:
    gate_id = refs["evidence_select"].value
    gate = next((g for g in state.gates if g.id == gate_id), None)
    if not gate:
        ui.notify("Select a gate first.", type="warning")
        return
    refs["dialog_title"].set_text(f"{gate.id} — {gate.gate}")
    refs["dialog_status"].set_text(gate.status.value)
    refs["dialog_evidence"].set_text(gate.evidence)
    refs["dialog_acceptance"].set_text(gate.acceptance or "Not specified.")
    refs["dialog_next"].set_text(gate.next_action or "No action recorded.")
    refs["evidence_dialog"].open()


async def handle_upload(event) -> None:
    try:
        raw = event.content.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        gates, errors = import_json_payload(raw)
        if not gates:
            ui.notify("Import rejected: " + "; ".join(errors[:3]), type="negative")
            return
        state.gates = gates
        refresh_all()
        message = f"Imported {len(gates)} gate(s)."
        if errors:
            message += f" {len(errors)} rejected."
        ui.notify(message, type="positive" if not errors else "warning")
    except Exception as exc:
        ui.notify(f"Import failed: {exc}", type="negative")


def download_text(filename: str, content: str) -> None:
    path = Path(tempfile.gettempdir()) / filename
    path.write_text(content, encoding="utf-8")
    ui.download(str(path))


def restore_seed() -> None:
    state.gates = parse_gates(load_snapshot(SNAPSHOT_PATH))
    refresh_all()
    ui.notify("Seed snapshot restored.", type="positive")


async def live_scan() -> None:
    button = refs["live_button"]
    button.disable()
    refs["live_status"].set_text("Running network checks…")
    try:
        live = await run.io_bound(run_live_checks, "https://aisearch.study")
        retained = [g for g in state.gates if not g.id.startswith("LIVE-") and not (g.id.startswith("TRUST-") and g.id not in {"TRUST-PAGES"})]
        state.gates = retained + live
        refresh_all()
        refs["live_status"].set_text(f"Live scan complete: {len(live)} evidence records.")
        ui.notify("Live domain checks completed.", type="positive")
    except Exception as exc:
        refs["live_status"].set_text(f"Live scan failed: {exc}")
        ui.notify("Live checks failed safely; no PASS state was invented.", type="negative")
    finally:
        button.enable()


ui.add_head_html("""
<style>
:root { color-scheme: light; }
body { background:#F8FAFC; color:#1E293B; }
.q-card { border-radius:16px; }
.metric-card { background:#fff; border:1px solid #E2E8F0; border-radius:16px; }
.panel { background:#fff; border:1px solid #E2E8F0; border-radius:16px; }
.brand-dot { width:42px;height:42px;border-radius:999px;background:#2563EB;display:grid;place-items:center;color:white;font-weight:800; }
</style>
""")

with ui.column().classes("mx-auto w-full max-w-[1500px] gap-5 p-4 md:p-6"):
    with ui.row().classes("w-full items-center justify-between gap-4 rounded-2xl bg-white p-5 shadow-sm"):
        with ui.row().classes("items-center gap-3"):
            ui.html('<div class="brand-dot">AI</div>')
            with ui.column().classes("gap-0"):
                ui.label("aisearch.study").classes("text-xl font-extrabold text-slate-900")
                refs["subtitle"] = ui.label(TEXT["ar"]["subtitle"]).classes("text-sm text-slate-500")
                ui.label("تعلّم بذكاء").classes("text-xs font-semibold text-blue-600")
        with ui.row().classes("items-center gap-3"):
            ui.label("aisearch.study").classes("hidden rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 md:block")
            ui.toggle({"en": "EN", "ar": "AR"}, value="ar", on_change=lambda e: set_locale(e.value)).props("dense")

    refs["disclaimer"] = ui.label(TEXT["ar"]["disclaimer"]).classes("w-full rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900")

    with ui.card().classes("w-full border border-red-200 bg-red-50 shadow-none") as decision_card:
        refs["decision_card"] = decision_card
        with ui.row().classes("w-full items-center justify-between gap-4"):
            with ui.column().classes("gap-1"):
                ui.label("Release Decision").classes("text-xs font-bold uppercase tracking-wider text-slate-500")
                refs["decision"] = ui.label("NO-GO").classes("text-3xl font-black text-red-700")
                refs["decision_reason"] = ui.label("").classes("text-sm text-slate-700")
            ui.label("GENERATED_ANSWERS_ENABLED=false").classes("rounded-lg bg-slate-900 px-3 py-2 font-mono text-xs text-white")

    with ui.grid(columns=4).classes("w-full gap-4 max-md:grid-cols-2 max-sm:grid-cols-1"):
        def metric_card(title: str, key: str, caption: str):
            with ui.card().classes("metric-card shadow-none"):
                ui.label(title).classes("text-xs font-semibold uppercase tracking-wide text-slate-500")
                refs[key] = ui.label("0").classes("text-3xl font-extrabold text-slate-900")
                ui.label(caption).classes("text-xs text-slate-500")
        metric_card("Blocking Gate Pass Rate", "kpi_blocking", "All blocking gates must PASS.")
        metric_card("Verified Pass Rate", "kpi_verified", "PASS + explicitly verified evidence.")
        metric_card("Trust Surface Completion", "kpi_trust", "Public trust/search controls.")
        metric_card("Blocking Gates Not Pass", "kpi_blockers", "PENDING / UNKNOWN / BLOCKED / FAIL.")

    with ui.card().classes("panel w-full shadow-none"):
        with ui.row().classes("w-full items-center justify-between gap-3"):
            with ui.column().classes("gap-1"):
                ui.label("Trust & Domain").classes("text-lg font-bold text-slate-900")
                refs["live_status"] = ui.label("Live checks are opt-in and fail closed.").classes("text-xs text-slate-500")
            refs["live_button"] = ui.button(TEXT["ar"]["run_live"], on_click=live_scan).props("outline color=primary")

    with ui.card().classes("panel w-full shadow-none"):
        refs["gates_heading"] = ui.label(TEXT["ar"]["gates"]).classes("text-lg font-bold text-slate-900")
        ui.label("Only PASS counts as pass. Imported data is validated before use.").classes("text-xs text-slate-500")
        with ui.grid(columns=4).classes("w-full gap-3 max-md:grid-cols-2 max-sm:grid-cols-1"):
            refs["filter_query"] = ui.input("Search", placeholder="SEC-REG / rate limit / evidence").props("dense outlined clearable")
            refs["filter_status"] = ui.select(["ALL", "PASS", "FAIL", "PENDING", "BLOCKED", "UNKNOWN"], value="ALL", label="Status").props("dense outlined")
            refs["filter_category"] = ui.select(["ALL"], value="ALL", label="Category").props("dense outlined")
            refs["filter_blocking"] = ui.select(["ALL", "YES", "NO"], value="ALL", label="Blocking").props("dense outlined")
        for key in ("filter_query", "filter_status", "filter_category", "filter_blocking"):
            refs[key].on_value_change(lambda _: refresh_table())
        columns = [
            {"name": "id", "label": "ID", "field": "id", "align": "left", "sortable": True},
            {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True},
            {"name": "gate", "label": "Gate", "field": "gate", "align": "left", "sortable": True},
            {"name": "status", "label": "Status", "field": "status", "align": "left", "sortable": True},
            {"name": "blocking", "label": "Blocking", "field": "blocking", "align": "left", "sortable": True},
            {"name": "verified", "label": "Verified", "field": "verified", "align": "left", "sortable": True},
            {"name": "next_action", "label": "Next action", "field": "next_action", "align": "left"},
        ]
        refs["gate_table"] = ui.table(columns=columns, rows=[], row_key="id", pagination=15).classes("w-full")
        refs["gate_table"].props("flat bordered dense wrap-cells")
        with ui.row().classes("w-full items-end gap-3"):
            refs["evidence_select"] = ui.select({}, label="Evidence record").classes("min-w-[320px] flex-1").props("outlined dense")
            ui.button("View evidence", on_click=show_evidence).props("outline color=primary")

    with ui.grid(columns=2).classes("w-full gap-4 max-lg:grid-cols-1"):
        with ui.card().classes("panel shadow-none"):
            refs["actions_heading"] = ui.label(TEXT["ar"]["actions"]).classes("text-lg font-bold text-slate-900")
            refs["actions_container"] = ui.column().classes("w-full gap-0")
        with ui.card().classes("panel shadow-none"):
            refs["invariants_heading"] = ui.label(TEXT["ar"]["invariants"]).classes("text-lg font-bold text-slate-900")
            refs["invariants_container"] = ui.column().classes("w-full gap-0")

    with ui.card().classes("panel w-full shadow-none"):
        ui.label("Import / Export").classes("text-lg font-bold text-slate-900")
        ui.label("Compatible with the Python control-plane JSON/CSV outputs.").classes("text-xs text-slate-500")
        with ui.row().classes("items-center gap-2"):
            ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.json max-files=1 max-file-size=1048576")
            refs["import_label"] = ui.label(TEXT["ar"]["import"]).classes("text-xs text-slate-500")
            btn_json = ui.button(on_click=lambda: download_text("aisearch-readiness.json", export_json(state.gates, state.metadata))).props("outline")
            with btn_json:
                refs["export_json_label"] = ui.label(TEXT["ar"]["export_json"])
            btn_csv = ui.button(on_click=lambda: download_text("aisearch-readiness.csv", export_csv(state.gates))).props("outline")
            with btn_csv:
                refs["export_csv_label"] = ui.label(TEXT["ar"]["export_csv"])
            btn_restore = ui.button(on_click=restore_seed).props("flat")
            with btn_restore:
                refs["restore_label"] = ui.label(TEXT["ar"]["restore"])

with ui.dialog() as evidence_dialog, ui.card().classes("w-[760px] max-w-[95vw]"):
    refs["evidence_dialog"] = evidence_dialog
    refs["dialog_title"] = ui.label("").classes("text-lg font-bold text-slate-900")
    refs["dialog_status"] = ui.label("").classes("w-fit rounded-full border px-2 py-1 text-xs font-bold")
    ui.separator()
    ui.label("Evidence").classes("text-xs font-bold uppercase text-slate-500")
    refs["dialog_evidence"] = ui.label("").classes("text-sm leading-relaxed text-slate-700")
    ui.label("Acceptance criteria").classes("text-xs font-bold uppercase text-slate-500")
    refs["dialog_acceptance"] = ui.label("").classes("text-sm leading-relaxed text-slate-700")
    ui.label("Next action").classes("text-xs font-bold uppercase text-slate-500")
    refs["dialog_next"] = ui.label("").classes("text-sm leading-relaxed text-slate-700")
    ui.button("Close", on_click=evidence_dialog.close).props("flat")

refresh_all()
set_locale("ar")

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="AISearch Study — Readiness Guardian", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False, show=False)
