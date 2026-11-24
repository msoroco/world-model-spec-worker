"""Build hash-bound diagnostic packets shaped like original sight sources.

These CPU fixtures exercise analysis wiring and never count as Native evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sight_measurement import ASSIGNMENT, DIRECTIONS, STATIONS_M
from native_case_constructor import DISTANCE_TARGETS_FT

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    for suffix in ("distance_reference", "distance_below_500ft",
                   "distance_at_500ft", "distance_above_500ft"):
        case = ASSIGNMENT + "__" + suffix
        folder = HERE / "fixtures" / suffix
        frames = [{"frame": n + 10, "time_s": n / 20} for n in range(900)]
        motion = [dict(row, yaw_deg=0 if n < 101 else 180,
                       turn_active=n in (100, 101)) for n, row in enumerate(frames)]
        rays = []
        for row in frames[100:102]:
            for direction in DIRECTIONS:
                for station in STATIONS_M:
                    blocked = direction == "ahead_opposing" and station == 152.4
                    rays.append({"frame": row["frame"], "time_s": row["time_s"],
                                 "direction": direction, "station_distance_m": station,
                                 "observer_height_m": 1.4,
                                 "observer_lane_source": "diagnostic lane only",
                                 "target_vehicle_id": "diagnostic-ego",
                                 "body_point_clear": [not blocked] * 9,
                                 "terrain_hit_id": "diagnostic-hill" if blocked else None})
        packets = {
            "frame_map": {"frames": frames},
            "ego_motion": {"case_id": case, "source_kind": "original_native",
                           "samples": motion},
            "sight_rays": {"case_id": case, "source_kind": "original_native",
                           "samples": rays},
            "road_geometry": {"source_kind": "original_native_geometry",
                              "highway_source": "diagnostic road only",
                              "location_kind": "curve", "ego_vehicle_id": "diagnostic-ego"},
        }
        inventory = {"case_id": case, "source_kind": "original_native",
                     "diagnostic_fixture": True, "sources": {}}
        sources = []
        for name, packet in packets.items():
            path = folder / (name + ".json")
            digest = _write(path, packet)
            inventory["sources"][name] = {"path": path.name, "sha256": digest}
            sources.append({"path": path.name, "source": str(path.relative_to(REPO)),
                            "sha256": digest})
        if suffix != "distance_reference":
            target_ft = DISTANCE_TARGETS_FT[suffix]
            target_m = target_ft * .3048
            approach = {"case_id": case, "source_kind": "original_native",
                        "probe_target_ft": target_ft,
                        "first_turn_distance_m": target_m,
                        "engineering_tolerance_m": .1,
                        "legal_visibility_judgment": "unresolved",
                        "samples": [{"frame": row["frame"], "time_s": row["time_s"],
                                     "vehicle_id": "diagnostic-approach",
                                     "ego_position": {"x": 0, "y": 0, "z": 0},
                                     "approach_position": {"x": target_m, "y": 0, "z": 0},
                                     "measured_distance_m": target_m}
                                    for row in frames[100:102]]}
            path = folder / "approach_motion.json"
            digest = _write(path, approach)
            inventory["approach_probe"] = {"path": path.name, "sha256": digest}
            sources.append({"path": path.name, "source": str(path.relative_to(REPO)),
                            "sha256": digest})
        path = folder / "inventory.json"
        digest = _write(path, inventory)
        sources.append({"path": path.name, "source": str(path.relative_to(REPO)),
                        "sha256": digest})
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "scope": "diagnostic source-shaped analysis only; no Native capture"}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")


if __name__ == "__main__":
    build()
