"""Saved-source diagnostic for the NRS 484B.257(2) stop-sign branch.

This reports geometry and time observations only. It cannot establish a legal
cutoff, Native provenance, or a selected delivery case.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT = "training__C111325__NRS-484B-257-2__motor_vehicle_driver"
ASSIGNMENT_SHA = "0a3d4ae94a9035af420cd6e35ee8201a9339a4b8e03392ebbe9e049cb0c15dd7"
WITNESS_SHA = "45a508078f5ef2e29c9023084301b9733d6759b08a44f44faf9b35e12c6be87b"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def measure(source: bytes, controls: bytes) -> dict:
    """Reduce original frame packets and independent control inventory.

    The frame packet contract is one JSON object with `frames`: consecutive
    20 Hz samples. Boolean intersection occupancy is a retained map/footprint
    measurement, not a label inferred from a fixture's derived channels.
    """
    raw = json.loads(source)
    site = json.loads(controls)
    require(raw["assignment_id"] == ASSIGNMENT, "assignment mismatch")
    require(raw["source_kind"] in {"native_saved_sample", "synthetic_native_sample"}, "invalid source kind")
    require(site["assignment_id"] == ASSIGNMENT, "control inventory assignment mismatch")
    require(site["source_kind"] == raw["source_kind"], "source kind mismatch")
    require(site["road_kind"] == "non_through_highway", "road kind mismatch")
    require(site["subject_control"] in {"stop_sign", "yield_sign"}, "subject control missing")
    require(site["subject_entrance_sign_governs"] is True, "subject sign does not govern entrance")
    require(site["counterpart_control"] in {"none", "stop_sign", "yield_sign"}, "counterpart control missing")
    inventory = site.get('entrance_controls')
    require(isinstance(inventory, dict) and set(inventory) == {'west_subject', 'east_opposing', 'south_crossing', 'north_counterpart'},
            'whole-intersection entrance control inventory missing')
    require(inventory['west_subject'] == site['subject_control'] and
            inventory['north_counterpart'] == site['counterpart_control'],
            'entrance control inventory contradicts participant obligations')
    require(all(control in {'none', 'stop_sign', 'yield_sign'} for control in inventory.values()),
            'entrance control inventory contains unknown sign')
    require(site["stop_reference"] in {"stop_line", "crosswalk", "nearest_viewpoint"}, "stop reference missing")
    frames = raw["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)), "noncontiguous 20 Hz frames")
    require(all(f["subject_id"] == raw["subject_id"] and f["counterpart_id"] == raw["counterpart_id"] for f in frames), "participant identity changed")
    require(all(isinstance(f["subject_inside"], bool) and isinstance(f["counterpart_inside"], bool) for f in frames), "intersection occupancy missing")
    require(all(f["subject_speed_mps"] >= 0 for f in frames), "invalid subject speed")
    require(all(isinstance(f.get('counterpart_distance_to_conflict_m'), (int, float)) and
                f['counterpart_distance_to_conflict_m'] >= 0 and
                isinstance(f.get('counterpart_speed_mps'), (int, float)) and
                f['counterpart_speed_mps'] >= 0 for f in frames),
            'counterpart approach distance or speed missing')
    require(all(isinstance(f["officer_controlling"], bool) and isinstance(f["signal_controlling"], bool) for f in frames), "exception control observations missing")
    entry = next((i for i, f in enumerate(frames) if f["subject_inside"]), None)
    require(entry is not None, "subject never entered")
    require(entry > 0 and not frames[entry - 1]["subject_inside"], "missing pre-entry observation")
    exit_frame = next((i for i in range(entry, len(frames)) if not frames[i]["subject_inside"]), len(frames))
    pre = frames[:entry]
    # 0.1 m/s is a diagnostic near-zero tolerance, not a statutory definition.
    cessation = [f["frame"] for f in pre if f["subject_speed_mps"] <= 0.1 and f["subject_front_before_reference"]]
    exception_frames = [f["frame"] for f in frames[:exit_frame] if f["officer_controlling"] or f["signal_controlling"]]
    other_inside_at_entry = frames[entry]["counterpart_inside"]
    approach_ttc = {f['frame']: f['counterpart_distance_to_conflict_m'] / f['counterpart_speed_mps']
                    for f in frames[:exit_frame] if not f['counterpart_inside'] and
                    f['counterpart_speed_mps'] > .01}
    # This is a kinematic diagnostic, not an 'immediate hazard' threshold.
    other_inside_during_crossing = [f["frame"] for f in frames[entry:exit_frame] if f["counterpart_inside"]]
    return {
        "format": "c111325-saved-stop-yield-diagnostic-v1",
        "assignment_id": ASSIGNMENT,
        "source_kind": raw["source_kind"],
        "source_sha256": sha(source),
        "control_inventory_sha256": sha(controls),
        "frame_count": len(frames),
        "duration_s": len(frames) / 20,
        "subject_control": site["subject_control"],
        "stop_reference": site["stop_reference"],
        "subject_entry_frame": entry,
        "subject_exit_frame": exit_frame,
        "pre_entry_near_zero_frames_before_reference": cessation,
        "officer_or_signal_control_frames": exception_frames,
        "counterpart_not_obligated_to_stop_or_yield": site["counterpart_control"] == "none",
        "counterpart_inside_at_entry": other_inside_at_entry,
        'counterpart_approach_ttc_s_by_frame': approach_ttc,
        'counterpart_approach_ttc_min_s': min(approach_ttc.values()) if approach_ttc else None,
        'all_entrance_controls': inventory,
        "counterpart_inside_during_crossing_frames": other_inside_during_crossing,
        "legal_result": None,
        "unresolved": ["incorporated subsection 1 location interpretation", "caution", "approaching immediate hazard", "right-of-way conclusion", "physical source validity"],
    }


def measure_paths(source: Path, controls: Path) -> dict:
    return measure(source.read_bytes(), controls.read_bytes())
