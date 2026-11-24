"""Audit fixed synthetic source conditions across exact saved comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import compare_exact


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def source_record(case_id: str) -> dict:
    suffix = case_id.removeprefix(HERE.name + "__")
    root = REPO / ".runtime-work/c109035-saved-proof" / suffix
    source = root / "source"
    receipt = json.loads((root / "versions/v0001/processing.json").read_text())
    if not receipt.get("passed") or not receipt.get("recorded_only"):
        raise ValueError("Saved-only source receipt missing: " + suffix)
    site = json.loads((source / "site_packet.json").read_text())
    equipment = json.loads((source / "equipment_record.json").read_text())
    config = json.loads((HERE / "constructions" / (suffix + ".json")).read_text())
    config = json.loads(next(f["content"] for f in config["files"] if f["path"] == "config.json"))
    actors = [json.loads(line) for line in (source / "actor_trace.jsonl").read_text().splitlines()]
    if len(actors) != 900 or site["case_id"] != case_id or equipment["case_id"] != case_id:
        raise ValueError("Source identity or frame count changed")
    site.pop("case_id")
    equipment.pop("case_id")
    case = config["case"]
    return {
        "case_id": case_id, "cell_id": config["cell_id"], "actor": config["actor"],
        "map_sha256": site["opendrive_sha256"],
        "site_sha256": digest(site),
        "route_sha256": digest([row["ego"]["x_m"] for row in actors]),
        "pedestrian_plan_sha256": digest([row["pedestrian"]["x_m"] for row in actors]),
        "equipment_record_sha256": digest(equipment),
        "capture_profile_sha256": digest(config["cameras"]),
        "weather_sha256": digest("weather unrecorded in synthetic fixture"),
        "ego_speed_policy_sha256": digest([row["ego"]["x_m"] for row in actors]),
        "requested_siren": case["siren"],
        "requested_warning_lamps": case["lamps"],
        "event_context": case["event"],
    }


def main() -> None:
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    receipts = []
    for item in plan["comparisons"]:
        records = [source_record(case_id) for case_id in item["case_ids"]]
        result = compare_exact(plan_path, item["comparison_id"], records)
        result["source_case_receipts"] = [
            {"case_id": record["case_id"],
             "processing_sha256": hashlib.sha256((REPO / ".runtime-work/c109035-saved-proof" /
                 record["case_id"].removeprefix(HERE.name + "__") /
                 "versions/v0001/processing.json").read_bytes()).hexdigest()}
            for record in records]
        result["weather_limit"] = "Synthetic fixture does not record weather; equal absence is not physical weather control"
        result["physical_acceptance_claimed"] = False
        receipts.append(result)
    target = HERE / "comparison-saved-receipts.json"
    target.write_text(json.dumps({"scope": "synthetic source join only", "comparisons": receipts}, indent=2) + "\n")
    print(json.dumps({"comparisons_passed": len(receipts),
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
