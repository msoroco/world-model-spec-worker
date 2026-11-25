"""Independent source-bound wide versus narrow caravan gap comparison."""
import argparse
import json
from pathlib import Path

from caravan_spacing import analyze


def _ids(root):
    first = json.loads((Path(root) / "caravan_history.jsonl").read_text().splitlines()[0])
    return ({member["actor_id"] for member in first["caravan_members"]},
            first["entering_vehicle"]["actor_id"])


def audit(wide_root, narrow_root, *, minimum_frames=900):
    wide_root, narrow_root = Path(wide_root), Path(narrow_root)
    wide, narrow = analyze(wide_root), analyze(narrow_root)
    if len(wide["samples"]) < minimum_frames or len(narrow["samples"]) < minimum_frames:
        raise ValueError("Full original-frame comparison duration required")
    fixed = ("native_map_id", "highway_id", "road_id", "outside_business_district",
             "caravan_or_motorcade", "roadway_polygon_xy_m", "road_forward_xy")
    contexts = [json.loads((root / "road_context.json").read_text()) for root in (wide_root, narrow_root)]
    if any(contexts[0].get(key) != contexts[1].get(key) for key in fixed):
        raise ValueError("Selected cases changed fixed highway or caravan context")
    if wide["context_source_hashes"] != narrow["context_source_hashes"]:
        raise ValueError("Selected cases changed original context sources")
    if _ids(wide_root) != _ids(narrow_root):
        raise ValueError("Selected cases changed original actors")
    if any(gap["entering_body_touches_member"] for result in (wide, narrow)
           for sample in result["samples"] for gap in sample["gaps"]):
        raise ValueError("Selected caravan comparison contains body contact")
    if not any(row["observed_entry_transition"] for row in wide["gap_occupancy"]):
        raise ValueError("Wide-gap entrant never entered and occupied")
    if narrow["gap_occupancy"]:
        raise ValueError("Narrow-gap entrant occupied a caravan gap")
    wide_opening = max(gap["longitudinal_opening_m"] for sample in wide["samples"] for gap in sample["gaps"])
    narrow_opening = max(gap["longitudinal_opening_m"] for sample in narrow["samples"] for gap in sample["gaps"])
    if not wide_opening > narrow_opening:
        raise ValueError("Selected cases did not vary physical opening")
    return {"format": "worker-caravan-gap-comparison", "wide_frames": len(wide["samples"]),
            "narrow_frames": len(narrow["samples"]), "wide_opening_m": wide_opening,
            "narrow_opening_m": narrow_opening, "wide_entry_observed": True,
            "narrow_occupancy_observed": False, "context_source_hashes": wide["context_source_hashes"],
            "physical_acceptance_claimed": False, "without_danger_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--narrow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.wide, args.narrow)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"wide_frames": result["wide_frames"],
                      "narrow_frames": result["narrow_frames"],
                      "comparison_passed": True}))
