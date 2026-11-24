"""CPU geometry diagnostic for a right-side passing corridor.

The result is a local geometric bound, not a statutory necessity finding.
"""

import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(folder):
    folder = Path(folder)
    sources = json.loads((folder / "sources.json").read_text())
    if sources.get("kind") != "synthetic_cpu_corridor":
        raise ValueError("Synthetic source provenance missing")
    for name in ("geometry.json", "actors.jsonl"):
        if sha256(folder / name) != sources["sha256"][name]:
            raise ValueError("Source hash differs: " + name)
    geo = json.loads((folder / "geometry.json").read_text())
    if geo.get("coordinate_frame") != "road_local_y_right_positive":
        raise ValueError("Road-local coordinate frame missing")
    left, right = geo["paved_y_m"]
    if not left < right or not geo["right_shoulder_y_m"][0] == right:
        raise ValueError("Pavement and shoulder boundaries inconsistent")
    if geo["right_shoulder_paved"] is not False:
        raise ValueError("Shoulder paving status unknown")
    ego_half = geo["ego_width_m"] / 2
    lead_half = geo["lead_width_m"] / 2
    overlap_limit = (geo["ego_length_m"] + geo["lead_length_m"]) / 2
    if min(ego_half, lead_half, overlap_limit, geo["clearance_m"]) <= 0:
        raise ValueError("Vehicle geometry or clearance invalid")
    rows = [json.loads(line) for line in (folder / "actors.jsonl").read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError("Expected 600 source samples for 30 seconds at 20 Hz")
    right_overlap = off_during_overlap = feasible_during_overlap = 0
    first, last = None, None
    min_margin = None
    for i, row in enumerate(rows):
        if row["frame"] != 1000 + i or abs(row["time_s"] - i / 20) > 1e-8:
            raise ValueError("Source frame/time join differs")
        if set(row["actors"]) != {"ego", "lead"}:
            raise ValueError("Ego or lead source missing")
        ego, lead = row["actors"]["ego"], row["actors"]["lead"]
        for actor in (ego, lead):
            if not isinstance(actor["x_m"], (int, float)) or not isinstance(actor["y_m"], (int, float)):
                raise ValueError("Actor pose missing")
        overlap = abs(ego["x_m"] - lead["x_m"]) <= overlap_limit
        if not overlap:
            continue
        if ego["y_m"] <= lead["y_m"]:
            raise ValueError("Overlap is not a right-side pass")
        right_overlap += 1
        first = row["frame"] if first is None else first
        last = row["frame"]
        off = ego["y_m"] + ego_half > right or ego["y_m"] - ego_half < left
        off_during_overlap += int(off)
        required_center = lead["y_m"] + lead_half + ego_half + geo["clearance_m"]
        paved_center_limit = right - ego_half
        margin = paved_center_limit - required_center
        min_margin = margin if min_margin is None else min(min_margin, margin)
        feasible_during_overlap += int(margin >= 0)
    if not right_overlap:
        raise ValueError("No right-side pass overlap in source")
    return {
        "source_kind": sources["kind"], "source_sha256": sources["sha256"],
        "frames": len(rows), "sample_rate_hz": 20,
        "right_pass_overlap_frames": right_overlap,
        "off_paved_during_right_pass_frames": off_during_overlap,
        "paved_right_corridor_feasible_frames": feasible_during_overlap,
        "minimum_paved_corridor_margin_m": round(min_margin, 6),
        "first_overlap_frame": first, "last_overlap_frame": last,
        "statutory_requires_condition": "unresolved",
        "physical_native_verified": False, "legal_verdict_claimed": False,
    }
