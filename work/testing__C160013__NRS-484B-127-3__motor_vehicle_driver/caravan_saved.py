"""Saved-only original-source outcome audit for the selected caravan pair."""
import argparse
import json
from pathlib import Path

from caravan_spacing import analyze

ASSIGNMENT = "testing__C160013__NRS-484B-127-3__motor_vehicle_driver"
WIDE = ASSIGNMENT + "__entrant_can_occupy_gap"
NARROW = ASSIGNMENT + "__entrant_cannot_occupy_gap"


def finalize(root, case_id, *, minimum_frames=900):
    if case_id not in (WIDE, NARROW):
        raise ValueError("Exact selected caravan case required")
    if type(minimum_frames) is not int or minimum_frames < 2:
        raise ValueError("Positive original-frame minimum required")
    observation = analyze(Path(root))
    samples = observation["samples"]
    if len(samples) < minimum_frames:
        raise ValueError("Incomplete original caravan capture")
    if not observation["caravan_forward_motion_observed"]:
        raise ValueError("Caravan forward motion absent on original frames")
    entry = any(row["observed_entry_transition"] for row in observation["gap_occupancy"])
    if case_id == WIDE and not entry:
        raise ValueError("Selected wide-gap entrant never entered and occupied")
    if case_id == NARROW and entry:
        raise ValueError("Selected narrow-gap entrant occupied caravan gap")
    contacts = sum(gap["entering_body_touches_member"] for sample in samples
                   for gap in sample["gaps"])
    if contacts:
        raise ValueError("Original entering body contacted caravan member")
    return {"format": "worker-caravan-saved-observations",
            "case_id": case_id, "original_frames": len(samples),
            "source_hashes": observation["sources"],
            "context_source_hashes": observation["context_source_hashes"],
            "wide_gap_entry_observed": entry if case_id == WIDE else None,
            "narrow_gap_occupancy_absent": not entry if case_id == NARROW else None,
            "contact_frames": contacts,
            "without_danger_judgment": "unresolved; source review required",
            "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("case_id", choices=(WIDE, NARROW))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(args.root, args.case_id)
    if args.output.exists():
        raise ValueError("Fresh saved observation output required")
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case_id, "original_frames": result["original_frames"],
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
