"""Audit the controlled Off-versus-operating signal comparison from saved sources."""

import argparse
import json
from pathlib import Path

from crossing_measurements import analyze


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(off_root: Path, operating_root: Path) -> dict:
    off_root, operating_root = Path(off_root), Path(operating_root)
    off = analyze(off_root, signal_mode="off")
    operating = analyze(operating_root, signal_mode="operating")
    for name in ("junction_context.json", "video_frames.jsonl"):
        if off["sources"][name] != operating["sources"][name]:
            raise ValueError("Fixed comparison source changed: " + name)
    off_rows = _rows(off_root / "crossing_history.jsonl")
    operating_rows = _rows(operating_root / "crossing_history.jsonl")
    if len(off_rows) != len(operating_rows):
        raise ValueError("Comparison frame count changed")
    for left, right in zip(off_rows, operating_rows):
        left, right = dict(left), dict(right)
        left.pop("signal_state", None)
        right.pop("signal_state", None)
        if left != right:
            raise ValueError("Comparison trajectory or source changed")
    for key in ("first_body_entry", "occupancy_intervals",
                "other_entered_before_ego_observed", "ego_approaching_at_other_entry_observed"):
        if off[key] != operating[key]:
            raise ValueError("Comparison observation changed: " + key)
    return {"format": "worker-signal-operation-comparison-observations",
            "source_sha256": {"off": off["sources"], "operating": operating["sources"]},
            "frame_count": len(off_rows),
            "off_states": sorted(set(off["observed_signal_states"])),
            "operating_states": sorted(set(operating["observed_signal_states"])),
            "fixed_trajectories_observed": True,
            "statutory_device_exception_judgment": "unresolved",
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("off_source_dir", type=Path)
    parser.add_argument("operating_source_dir", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    report = audit(args.off_source_dir, args.operating_source_dir)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
