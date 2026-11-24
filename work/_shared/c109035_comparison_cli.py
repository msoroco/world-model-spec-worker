"""Audit C109035 comparisons from sealed original local attempts.

The attempt map is JSON from exact case IDs to original attempt directories.
The output is a source join. It does not assert audibility or a legal verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ASSIGNMENT = "testing__C109035__NRS-484D-400-5__emergency_vehicle_driver"
PACKAGE = REPO / "work" / ASSIGNMENT
sys.path.insert(0, str(PACKAGE))

from comparison_audit import compare_exact  # noqa: E402
from saved_finalizer import _read, finalize  # noqa: E402


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def source_record(case_id: str, attempt: Path) -> tuple[dict, dict]:
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("Comparison case is outside C109035")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    attempt = Path(attempt).resolve(strict=True)
    saved = finalize(attempt, case_id=case_id)
    receipt_bytes = (attempt / "capture_receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("case_id") != case_id or receipt.get("physical_acceptance_claimed") is not False:
        raise ValueError("Original capture receipt differs")
    site = json.loads(_read(attempt, receipt["sources"]["site_packet"]))
    equipment = json.loads(_read(attempt, receipt["sources"]["equipment_record"]))
    if site.get("case_id") != case_id or equipment.get("case_id") != case_id:
        raise ValueError("Original site or equipment case differs")
    construction = json.loads((PACKAGE / "constructions" / (suffix + ".json")).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    if config.get("selected_case_id") != case_id:
        raise ValueError("Selected construction case differs")
    site_without_case = {key: value for key, value in site.items() if key != "case_id"}
    equipment_without_case = {key: value for key, value in equipment.items()
                              if key != "case_id"}
    knobs = config["case"]
    record = {
        "case_id": case_id,
        "cell_id": config["cell_id"],
        "actor": config["actor"],
        "map_sha256": site["opendrive_sha256"],
        "site_sha256": digest(site_without_case),
        "route_sha256": digest((site["approach"], site["ego_transform"])),
        "pedestrian_plan_sha256": digest(site["pedestrian_transform"]),
        "equipment_record_sha256": digest(equipment_without_case),
        "capture_profile_sha256": digest(config["cameras"]),
        "weather_sha256": digest("weather not source-bound by this comparison"),
        "ego_speed_policy_sha256": digest(config.get("ego_speed_policy", "same authored policy")),
        "requested_siren": knobs["siren"],
        "requested_warning_lamps": knobs["lamps"],
        "event_context": knobs["event"],
    }
    provenance = {
        "case_id": case_id,
        "capture_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "saved_source_sha256": saved["source_sha256"],
    }
    return record, provenance


def audit(comparison_id: str, attempt_map: dict[str, str]) -> dict:
    plan_path = PACKAGE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    matches = [item for item in plan["comparisons"]
               if item["comparison_id"] == comparison_id]
    if len(matches) != 1:
        raise ValueError("Exact comparison absent or ambiguous")
    expected = matches[0]["case_ids"]
    if set(attempt_map) != set(expected) or len(attempt_map) != len(expected):
        raise ValueError("Attempt map must cover exact comparison cases")
    pairs = [source_record(case_id, Path(attempt_map[case_id])) for case_id in expected]
    result = compare_exact(plan_path, comparison_id, [record for record, _ in pairs])
    result["original_source_receipts"] = [provenance for _, provenance in pairs]
    result["weather_limit"] = "Original weather equality is not established by this source join"
    result["physical_acceptance_claimed"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.comparison, json.loads(args.attempt_map.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "case_count": len(result["case_ids"]),
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
