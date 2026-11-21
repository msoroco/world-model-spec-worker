"""Audit controlled signal and entry-order comparisons from saved sources."""

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


def audit_entry_order(other_first_root: Path, ego_first_root: Path) -> dict:
    other_first_root, ego_first_root = Path(other_first_root), Path(ego_first_root)
    other_first = analyze(other_first_root, signal_mode="off")
    ego_first = analyze(ego_first_root, signal_mode="off")
    for name in ("junction_context.json", "video_frames.jsonl"):
        if other_first["sources"][name] != ego_first["sources"][name]:
            raise ValueError("Fixed entry-order source changed: " + name)
    if other_first["other_entered_before_ego_observed"] is not True:
        raise ValueError("Other-first entry order not observed")
    if ego_first["other_entered_before_ego_observed"] is not False:
        raise ValueError("Ego-first entry order not observed")
    left_rows = _rows(other_first_root / "crossing_history.jsonl")
    right_rows = _rows(ego_first_root / "crossing_history.jsonl")
    if len(left_rows) != len(right_rows):
        raise ValueError("Entry-order frame count changed")
    dynamic = {"body_vertices_xy_m", "distance_to_intersection_m", "speed_mps"}
    for left, right in zip(left_rows, right_rows):
        for who in ("ego", "other"):
            left_actor, right_actor = left[who], right[who]
            if ({key: value for key, value in left_actor.items() if key not in dynamic} !=
                    {key: value for key, value in right_actor.items() if key not in dynamic}):
                raise ValueError("Fixed entry-order actor source changed")
            left = dict(left)
            right = dict(right)
            left.pop(who)
            right.pop(who)
        if left != right:
            raise ValueError("Fixed entry-order frame or signal source changed")
    return {"format": "worker-entry-order-comparison-observations",
            "source_sha256": {"other_first": other_first["sources"], "ego_first": ego_first["sources"]},
            "frame_count": len(left_rows),
            "first_body_entry": {"other_first": other_first["first_body_entry"],
                                 "ego_first": ego_first["first_body_entry"]},
            "fixed_junction_frames_signal_and_actor_identity_observed": True,
            "right_of_way_judgment": "unresolved",
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("off_source_dir", type=Path)
    parser.add_argument("operating_source_dir", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--entry-order", action="store_true")
    args = parser.parse_args()
    report = (audit_entry_order(args.off_source_dir, args.operating_source_dir)
              if args.entry_order else audit(args.off_source_dir, args.operating_source_dir))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
