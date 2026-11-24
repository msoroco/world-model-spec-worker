"""CPU saved-source measurement for the NRS 484B.510 draft.

The inputs are retained raw observations, not Core-derived channels.  A purpose
declaration is recorded as context and is never inferred from motion or pixels.
This module makes measurements only; it does not decide legality or sign authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FRAME_COUNT = 600
FRAME_RATE = 20
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_bundle(root: Path) -> tuple[dict, list[dict], dict[str, str]]:
    paths = {name: root / name for name in ("zone.json", "raw-frames.json")}
    for name, path in paths.items():
        require(path.is_file(), f"missing required raw source: {name}")
    zone = json.loads(paths["zone.json"].read_text())
    frames = json.loads(paths["raw-frames.json"].read_text())
    require(zone.get("source_kind") == "synthetic_native_sample", "source kind must be explicit")
    require(zone.get("restricted_purpose"), "restricted purpose absent")
    require(zone.get("sign_text"), "sign text absent")
    require(zone.get("zone_bounds_m"), "zone bounds absent")
    require(zone.get("sign_authority") == "unverified", "synthetic fixture cannot establish sign authority")
    require(isinstance(frames, list) and len(frames) == FRAME_COUNT, "expected 600 raw frames")
    for i, frame in enumerate(frames):
        require(frame.get("frame") == i, f"frame identity mismatch at {i}")
        require(frame.get("elapsed_s") == i / FRAME_RATE, f"frame clock mismatch at {i}")
        require(tuple(frame.get("camera_ids", ())) == CAMERAS, f"four camera identities absent at {i}")
        for field in ("ego_footprint_m", "ego_speed_mps", "door_open", "occupant_count",
                      "pedestrian_count", "other_vehicle_waiting", "other_vehicle_about_to_enter"):
            require(field in frame, f"raw field {field} absent at {i}")
        footprint = frame["ego_footprint_m"]
        require(len(footprint) == 4, f"ego footprint missing at {i}")
        require(isinstance(frame["occupant_count"], int) and frame["occupant_count"] >= 0,
                f"invalid occupant count at {i}")
    return zone, frames, {name: digest(path) for name, path in paths.items()}


def derive(root: Path) -> dict:
    zone, frames, hashes = load_bundle(root)
    x0, y0, x1, y1 = zone["zone_bounds_m"]
    require(x0 < x1 and y0 < y1, "invalid zone geometry")
    in_zone, stopped, passenger_activity, conflict = [], [], [], []
    for frame in frames:
        fx0, fy0, fx1, fy1 = frame["ego_footprint_m"]
        inside = x0 <= fx0 <= fx1 <= x1 and y0 <= fy0 <= fy1 <= y1
        stationary = frame["ego_speed_mps"] <= 0.05
        in_zone.append(inside)
        stopped.append(inside and stationary)
        conflict.append(bool(frame["other_vehicle_waiting"] or frame["other_vehicle_about_to_enter"]))
    for i, frame in enumerate(frames):
        prior = frames[i - 1]["occupant_count"] if i else frame["occupant_count"]
        passenger_activity.append(bool(frame["door_open"] and
                                       (frame["pedestrian_count"] > 0 or frame["occupant_count"] != prior)))
    stopped_indices = [i for i, value in enumerate(stopped) if value]
    passenger_indices = [i for i, value in enumerate(passenger_activity) if value and stopped[i]]
    conflict_indices = [i for i, value in enumerate(conflict) if value and stopped[i]]
    return {
        "format": "restricted-zone-saved-measurement-v1",
        "source_kind": "synthetic_native_sample",
        "source_sha256": hashes,
        "frame_count": FRAME_COUNT,
        "frame_rate_hz": FRAME_RATE,
        "camera_ids": list(CAMERAS),
        "restricted_purpose": zone["restricted_purpose"],
        "sign_text": zone["sign_text"],
        "sign_authority": "unverified",
        "subject_purpose_declaration": zone.get("subject_purpose_declaration"),
        "subject_purpose_is_observed": False,
        "in_zone_frames": sum(in_zone),
        "stopped_in_zone_frames": len(stopped_indices),
        "stopped_in_zone_duration_s": len(stopped_indices) / FRAME_RATE,
        "stopped_interval_first_frame": stopped_indices[0] if stopped_indices else None,
        "stopped_interval_last_frame": stopped_indices[-1] if stopped_indices else None,
        "passenger_activity_frames_while_stopped": len(passenger_indices),
        "passenger_activity_first_frame": passenger_indices[0] if passenger_indices else None,
        "occupant_count_start": frames[0]["occupant_count"],
        "occupant_count_end": frames[-1]["occupant_count"],
        "waiting_or_entering_vehicle_frames_while_stopped": len(conflict_indices),
        "waiting_or_entering_vehicle_first_frame": conflict_indices[0] if conflict_indices else None,
        "exception_temporariness_judgment": "unreviewed",
        "legal_conclusion": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(derive(args.bundle), sort_keys=True))
