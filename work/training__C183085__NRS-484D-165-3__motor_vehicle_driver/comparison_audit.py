"""Independently compare four exact shoulder lamp case groups."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, a_processing, b_processing, a_audit, b_audit,
          c_processing, c_audit, diagnostic, omit_b):
    plan = read(ROOT / "case-plan.json")
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None or len(comparison["case_ids"]) not in (2, 3):
        raise ValueError("Selected comparison identity differs")
    if omit_b:
        raise ValueError("Missing independent B audit")
    audit_paths = [a_audit, b_audit] + ([c_audit] if c_audit else [])
    processing_paths = [a_processing, b_processing] + ([c_processing] if c_processing else [])
    if len(audit_paths) != len(comparison["case_ids"]) or \
            len(processing_paths) != len(comparison["case_ids"]):
        raise ValueError("Comparison case count differs")
    audits = [read(path) for path in audit_paths]
    saved = [read(path) for path in processing_paths]
    if ([item.get("case_id") for item in audits] != comparison["case_ids"] or
            [item.get("case_id") for item in saved] != comparison["case_ids"] or
            any(item.get("diagnostic_only") is not diagnostic for item in audits) or
            any(item.get("passed") is not True or item.get("missing_evidence") is not False
                for item in saved)):
        raise ValueError("Independent case audits or saved receipts differ")
    stages = [Path(item["analysis_directory"]) for item in saved]
    configs = [read(path / "config.json") for path in stages]
    reports = [read(path / "analysis-report.json") for path in stages]
    for config in configs[1:]:
        for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                    "cameras", "frozen_cell", "vehicle_blueprint", "required_atoms"):
            if config[key] != configs[0][key]:
                raise ValueError("Fixed comparison condition differs: " + key)
    if any(report.get("legal_verdict_claimed") is not False for report in reports):
        raise ValueError("Legal verdict claimed without original review")
    deliberate = comparison["deliberate_differences"]
    if len(deliberate) != 1:
        raise ValueError("One controlled comparison variable required")
    variable = deliberate[0]
    for config in configs[1:]:
        for key in ("lamp_command", "optical_target_kind", "target_distance_ft"):
            if (variable == "parked_lamp_display" and key == "lamp_command") or \
                    (variable != "parked_lamp_display" and key == "target_distance_ft"):
                continue
            if config[key] != configs[0][key]:
                raise ValueError("Uncontrolled case configuration differs: " + key)
    if variable == "parked_lamp_display":
        measured = [report["source_join"]["position_command_omission_frames"]
                    for report in reports]
        if [len(value) for value in measured] != [0, 600]:
            raise ValueError("Full-interval lamp command contrast missing")
        values = [len(value) for value in measured]
    else:
        kind = {"ambient_reveal_distance": "ambient_reveal",
                "front_lamp_visibility": "front_white_or_amber",
                "rear_lamp_visibility": "rear_red"}[variable]
        values = [report["source_join"]["optical_brackets"][kind]["estimate_ft"]
                  for report in reports]
        if values != sorted(values) or len(set(values)) != 3:
            raise ValueError("Numeric optical source probes differ")
        for config, value in zip(configs, values):
            if config["target_distance_ft"] != value:
                raise ValueError("Requested target differs from synthetic source measurement")
    return {"format": "c183085-independent-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "fixed_conditions": comparison["fixed_conditions"],
            "deliberate_differences": deliberate, "measured_values": values,
            "saved_processing_sha256": [sha(path) for path in processing_paths],
            "delivery_audit_sha256": [sha(path) for path in audit_paths],
            "diagnostic_only": diagnostic, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    for name in ("comparison_id", "a_processing", "b_processing", "a_audit",
                 "b_audit", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--c-processing")
    parser.add_argument("--c-audit")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-b-audit", action="store_true")
    args = parser.parse_args()
    result = audit(args.comparison_id, args.a_processing, args.b_processing,
                   args.a_audit, args.b_audit, args.c_processing, args.c_audit,
                   args.diagnostic, args.omit_b_audit)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous comparison audit result")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison_id": args.comparison_id}))


if __name__ == "__main__":
    main()
