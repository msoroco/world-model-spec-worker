"""Check the four selected taxi comparisons on source-bound CPU diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    reports = {}
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        folder = ROOT / "cases" / suffix
        report_path = folder / "diagnostic-analysis-report.json"
        compatibility = json.loads((folder / "primary-compatibility.json").read_text())
        if sha(report_path) != compatibility["analysis_report_sha256"]:
            raise ValueError("diagnostic report differs from pinned compatibility: " + suffix)
        report = json.loads(report_path.read_text())
        if report.get("case_id") != case_id or report.get("legal_verdict") is not None:
            raise ValueError("wrong case or unsupported legal verdict: " + suffix)
        reports[suffix] = report

    def value(suffix: str, key: str):
        return reports[suffix]["measurements"][key]["value"]

    designated = value("designated_stand_park", "taxi_stand_context")
    outside = value("outside_stand_park", "taxi_stand_context")
    if not designated["all_halt_footprints_inside_designated_stand"] or not outside["all_halt_footprints_outside_designated_stand"]:
        raise ValueError("stand designation comparison collapsed")
    park = value("outside_stand_park", "taxi_halt_activity")
    stand = value("outside_stand_stand", "taxi_halt_activity")
    if (park["reviewed_activity"], stand["reviewed_activity"]) != ("park", "stand"):
        raise ValueError("parking versus standing activity collapsed")
    load = value("outside_stand_load", "taxi_passenger_exception")
    unload = value("outside_stand_unload", "taxi_passenger_exception")
    idle = value("outside_stand_idle_stop", "taxi_passenger_exception")
    if (load["passenger_event_kinds"], unload["passenger_event_kinds"], idle["passenger_event_kinds"]) != (["boarding"], ["alighting"], []):
        raise ValueError("passenger exchange comparison collapsed")
    if not load["expeditiousness_review_required"] or not unload["expeditiousness_review_required"]:
        raise ValueError("expeditiousness review obligation lost")
    if not park["footprints_outside_stand"] or not load["other_regulation_review_required"]:
        raise ValueError("parking/loading shared context lost")
    receipt = {"format": "worker-diagnostic-comparison-audit", "assignment_id": ROOT.name,
               "passed": True, "scope": "synthetic source-gated CPU fixture only; no legal verdict",
               "comparison_ids": [item["comparison_id"] for item in plan["comparisons"]],
               "analysis_report_sha256": {suffix: sha(ROOT / "cases" / suffix / "diagnostic-analysis-report.json")
                                          for suffix in reports},
               "remaining": ["Original site, stand and taxi source review",
                             "Native passenger exchange and pixel review",
                             "Source-reviewed expeditiousness and other-rule judgments"]}
    (ROOT / "comparison-audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("four source-bound taxi diagnostic comparisons passed; no legal verdict claimed")


if __name__ == "__main__":
    build()
