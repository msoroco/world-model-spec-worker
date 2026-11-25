"""Create explicitly synthetic, source-shaped stand compatibility inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_bundles import HERE, AID

REPO = HERE.parents[1]
VIDEO_PROBE = REPO / ".runtime-work" / "c135087-fixture-video-probe"
VIEWS = (("overview", 1920, 1080, "black"), ("approach", 1280, 720, "blue"),
         ("reference_corner", 1280, 720, "green"), ("driver_reference", 1280, 720, "red"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value), encoding="utf-8")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    hashes = {name: sha((VIDEO_PROBE / (name + ".mkv")).read_bytes()) for name, _, _, _ in VIEWS}
    for case in plan["cases"]:
        cid = case["case_id"]
        suffix = cid.removeprefix(AID + "__")
        folder = HERE / "diagnostics" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        site = {"format": "synthetic_fixture_site_only", "kind": "taxicab_stand", "cell_id": "C135087",
                "map_name": "SyntheticStandTown", "highway_status_source": "DIAGNOSTIC FIXTURE ONLY",
                "designation_source": "DIAGNOSTIC FIXTURE ONLY", "sign_source": "DIAGNOSTIC FIXTURE ONLY",
                "lane_id": 1, "curb_polygon": [[0, 0], [4, 0], [4, 5], [0, 5]],
                "approach_lane_id": 2, "access_waypoints": [[0, -10], [0, 0]],
                "stand_waypoint": [1, 1], "passenger_waypoint": [2, 1], "sign_id": "fixture-sign"}
        vehicles = {"format": "synthetic_fixture_vehicle_roles_only",
                    "subject": {"kind": "passenger_vehicle", "compensated_taxicab_use": False,
                                "driver_identity_source": "DIAGNOSTIC FIXTURE ONLY", "blueprint": "fixture-sedan"},
                    "entrant": {"kind": "motor_vehicle", "design_capacity_including_driver": 5,
                                "compensated_passenger_use_source": "DIAGNOSTIC FIXTURE ONLY", "blueprint": "fixture-taxi"}}
        rows = []
        for index in range(900):
            active = case["loading_mode"] == "active" and index < 500
            approaching = case["entrant_mode"] == "about_to_enter" and index < 300
            waiting = case["entrant_mode"] == "waiting_to_enter" and index >= 200
            position_x = min(index / 20, 2.0)
            rows.append({"frame": 100 + index, "time_s": index / 20,
                         "case_id": cid, "map_name": site["map_name"],
                         "subject_id": 10, "entrant_id": 11, "passenger_id": 12,
                         "subject_speed_mps": 0 if index >= 40 else 1,
                         "entrant_speed_mps": 0 if waiting else 2,
                         "passenger_loading_active": active, "entrant_waiting": waiting,
                         "entrant_about_to_enter": approaching,
                         "access_obstructed": case["access_mode"] == "constrained" and index >= 40,
                         "position": {"x": position_x, "y": 1.0, "z": 0.0},
                         "heading_deg": 0.0})
        frame_map = [{"frame": row["frame"], "time_s": row["time_s"]} for row in rows]
        trace = "".join(encode({key: row[key] for key in ("frame", "time_s", "position", "heading_deg")}
                               | {"position_m": [row["position"][key] for key in ("x", "y", "z")],
                                  "speed_mps": row["subject_speed_mps"],
                                  "speed_mph": row["subject_speed_mps"] / .44704}) for row in rows)
        video_map = "".join(encode({"video_frame": index, "carla_frame": row["frame"], "time_s": row["time_s"]})
                            for index, row in enumerate(rows))
        actor_text = encode(rows)
        map_text = encode(frame_map)
        attempt = {"source_format": "native_original", "frame_count": 900, "fps": 20,
                   "case_id": cid, "map_name": site["map_name"],
                   "subject_id": 10, "entrant_id": 11, "passenger_id": 12, "first_frame": 100,
                   "actor_rows": {"path": "actor-rows.json", "sha256": sha(actor_text.encode())},
                   "frame_map": {"path": "frame-map.json", "sha256": sha(map_text.encode())},
                   "cameras": {name: {"path": name + ".mkv", "sha256": hashes[name],
                                        "frame_count": 900, "fps": 20} for name, _, _, _ in VIEWS}}
        texts = {"site-original.json": encode(site), "vehicle-original.json": encode(vehicles),
                 "actor-rows.json": actor_text, "frame-map.json": map_text,
                 "attempt-source.json": encode(attempt), "trace.jsonl": trace,
                 "video_frames.jsonl": video_map,
                 "acquisition-provenance.json": encode({"provenance_kind": "synthetic_fixture",
                                                         "diagnostic_fixture": True,
                                                         "scope": "Software diagnostic only; no original site or CARLA capture"})}
        for name, content in texts.items():
            (folder / name).write_text(content, encoding="utf-8")
        generator = {"files": {}, "graphs": [],
                     "videos": [{"path": name + ".mkv", "frames": 900, "width": width,
                                 "height": height, "fps": 20, "color": color}
                                for name, width, height, color in VIEWS]}
        generator_path = HERE / "diagnostics" / (suffix + "-generator.json")
        write(generator_path, generator)
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": str(generator_path.relative_to(REPO)),
                                "sha256": sha(generator_path.read_bytes())},
                  "sources": [{"path": name, "source": str((folder / name).relative_to(REPO)),
                               "sha256": sha(content.encode())}
                              for name, content in texts.items()]}
        write(HERE / "diagnostics" / (suffix + "-recipe.json"), recipe)
    print("built", len(plan["cases"]), "synthetic-only source-shaped recipes")


if __name__ == "__main__":
    build()
