"""Compare observed officer contexts from two saved exact-case captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from officer_motion import measure
from officer_scene import CASES
from officer_site_packet import validate_packet

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed(stage: Path, expected: str, diagnostic: bool):
    suffix = expected.removeprefix(ASSIGNMENT + "__")
    case = next((item for item in CASES if item.suffix == suffix), None)
    if case is None:
        raise ValueError("comparison names unknown exact case")
    seal = json.loads((stage / "capture-seal.json").read_text())
    report = json.loads((stage / "analysis-report.json").read_text())
    if (seal.get("case_id") != expected or report.get("case_id") != expected or
            seal.get("diagnostic_fixture") is not diagnostic or
            report.get("legal_verdict_claimed") is not False):
        raise ValueError("comparison source identity differs")
    inventory = seal.get("source_sha256", {})
    if not inventory or any(sha(stage / name) != digest for name, digest in inventory.items()):
        raise ValueError("comparison original source changed")
    site = validate_packet(stage / "original-attempt/site-packet.json", expected)
    history = json.loads((stage / "original-attempt/history.json").read_text())
    values = measure(history, site, case, diagnostic_fixture=diagnostic)
    if report.get("measurements", {}).get("officer_intersection_motion", {}).get("value", {}).get("motion") != values:
        raise ValueError("saved source measurement differs")
    return {"case_id": expected, "site": site, "motion": values,
            "seal_sha256": sha(stage / "capture-seal.json"),
            "report_sha256": sha(stage / "analysis-report.json")}


def audit(comparison_id: str, left: Path, right: Path, diagnostic: bool):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    comparison = next((item for item in plan["comparisons"] if item["comparison_id"] == comparison_id), None)
    if comparison is None or len(comparison["case_ids"]) != 2:
        raise ValueError("unknown exact comparison")
    a = observed(left, comparison["case_ids"][0], diagnostic)
    b = observed(right, comparison["case_ids"][1], diagnostic)
    fixed = ("ego_route_xy", "other_route_source_sha256", "officer_spawn_xy",
             "intersection_entry_station_m", "entrances", "layout", "maneuver")
    if any(a["site"][key] != b["site"][key] for key in fixed):
        raise ValueError("comparison fixed scene changed")
    am, bm = a["motion"], b["motion"]
    if comparison_id.endswith("officer_directive"):
        if (am["observed_officer_directive_at_entry"],
                bm["observed_officer_directive_at_entry"]) != ("stop", "proceed") or \
                am["observed_other_phase_at_entry"] != bm["observed_other_phase_at_entry"]:
            raise ValueError("observed officer directive difference missing")
    elif comparison_id.endswith("distance"):
        if (bm["observed_other_center_station_at_entry_m"] -
                am["observed_other_center_station_at_entry_m"] < 20 or
                am["observed_officer_directive_at_entry"] !=
                bm["observed_officer_directive_at_entry"] or
                am["observed_other_phase_at_entry"] != bm["observed_other_phase_at_entry"]):
            raise ValueError("observed counterpart station difference missing")
    elif comparison_id == "within_vs_approaching":
        if (am["observed_other_phase_at_entry"],
                bm["observed_other_phase_at_entry"]) != ("within", "approaching") or \
                am["observed_officer_directive_at_entry"] != bm["observed_officer_directive_at_entry"]:
            raise ValueError("observed counterpart phase difference missing")
    else:
        raise ValueError("comparison difference rule undefined")
    return {"format": "c157964-saved-comparison-v1", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "diagnostic_fixture": diagnostic,
            "observed": [{"case_id": item["case_id"], "motion": item["motion"],
                          "seal_sha256": item["seal_sha256"],
                          "report_sha256": item["report_sha256"]} for item in (a, b)],
            "fixed_conditions_checked": list(fixed), "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left, args.right, args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError("refusing to replace comparison audit")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["comparison_id"])
