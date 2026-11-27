"""Independent paired source audit for pedestrian conflict response."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPARISON = ROOT.name + "__selected_90e3f1aa__comparison"


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(a_processing, b_processing, a_audit, b_audit, diagnostic, omit_b):
    plan = read(ROOT / "case-plan.json")
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == COMPARISON), None)
    if comparison is None or len(comparison["case_ids"]) != 2:
        raise ValueError("Selected comparison identity differs")
    if omit_b:
        raise ValueError("Missing independent B audit")
    audits = [read(a_audit), read(b_audit)]
    saved = [read(a_processing), read(b_processing)]
    if ([item.get("case_id") for item in audits] != comparison["case_ids"] or
            [item.get("case_id") for item in saved] != comparison["case_ids"] or
            any(item.get("diagnostic_only") is not diagnostic for item in audits) or
            any(item.get("passed") is not True or item.get("missing_evidence") is not False
                for item in saved)):
        raise ValueError("Independent case audits or saved receipts differ")
    stages = [Path(item["analysis_directory"]) for item in saved]
    configs = [read(path / "config.json") for path in stages]
    reports = [read(path / "analysis-report.json") for path in stages]
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        if configs[0][key] != configs[1][key]:
            raise ValueError("Fixed comparison condition differs: " + key)
    if (configs[0]["controller"] != "distance_triggered_slow_request" or
            configs[1]["controller"] != "maintain_request" or
            reports[0]["source_hashes"]["road_survey.json"] !=
            reports[1]["source_hashes"]["road_survey.json"]):
        raise ValueError("Pedestrian context or deliberate controller difference changed")
    # Requested controls are source observations, not a legal outcome.
    diagnostics = [read(path / "result.json")["physical_observations"]["due_care_diagnostics"]
                   for path in stages]
    if (diagnostics[0]["requested_brake_frames"] <= 0 or
            diagnostics[1]["requested_brake_frames"] != 0 or
            any(item["legal_due_care_verdict"] is not None for item in diagnostics)):
        raise ValueError("Original requested-response comparison differs")
    return {"format": "c230266-independent-comparison-audit-v1", "comparison_id": COMPARISON,
            "case_ids": comparison["case_ids"], "fixed_conditions": comparison["fixed_conditions"],
            "deliberate_differences": comparison["deliberate_differences"],
            "requested_brake_frames": [item["requested_brake_frames"] for item in diagnostics],
            "saved_processing_sha256": [sha(path) for path in (a_processing, b_processing)],
            "delivery_audit_sha256": [sha(path) for path in (a_audit, b_audit)],
            "diagnostic_only": diagnostic, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    for name in ("a_processing", "b_processing", "a_audit", "b_audit", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-b-audit", action="store_true")
    args = parser.parse_args()
    result = audit(args.a_processing, args.b_processing, args.a_audit, args.b_audit,
                   args.diagnostic, args.omit_b_audit)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous comparison audit result")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison_id": COMPARISON}))


if __name__ == "__main__":
    main()
