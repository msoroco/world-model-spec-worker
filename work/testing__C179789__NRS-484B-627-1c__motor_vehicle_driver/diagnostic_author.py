"""Author bounded exact route software fixtures from an existing diagnostic seed.

These fixtures are synthetic projections for software compatibility only.
They do not provide original C179789 highway, route, follower or camera evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SEED = REPO / "work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/diagnostic-crosswalk_clear_turn.json"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic source exceeds 2 MiB")


def main() -> None:
    seed = json.loads(SEED.read_text())
    mapping = [json.loads(line) for line in seed["files"]["video_frames.jsonl"].splitlines()]
    if len(mapping) != 9:
        raise ValueError("nine diagnostic frames required")
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        spec = json.loads(SEED.read_text())
        target = case["target"]
        site = {"diagnostic_fixture": True, "reviewed_original_site": False,
                "case_id": case_id, "controlled_access": target["controlled_access"],
                "alternate_declared": target["alternate_declared"],
                "alternate_restriction_state": "open" if target["alternate_declared"] else "restricted",
                "requested_route_choice": target["route_choice"],
                "synthetic_source_only": "No original C179789 map, route or legal source is supplied."}
        site_text = json.dumps(site, sort_keys=True) + "\n"
        rows = []
        body_rows = []
        for index, frame in enumerate(mapping):
            x = float(index * 2)
            body = [[x+dx, dy] for dx in (-1.0, 1.0) for dy in (-0.5, 0.5) for _ in (0, 1)]
            rows.append({"original_frame": frame["carla_frame"], "time_s": frame["time_s"],
                         "ego_id": "diagnostic-ego", "follower_id": "diagnostic-follower",
                         "ego_xy": [x, 0.0], "follower_xy": [x-10.0, 0.0],
                         "following_gap_m": 10.0,
                         "ego_speed_mps": float(target.get("ego_speed_mps") or 5.0),
                         "follower_speed_mps": 7.0,
                         "ego_route_station_m": x, "follower_route_station_m": x-10.0,
                         "actual_route_choice": target["route_choice"],
                         "controlled_access": target["controlled_access"],
                         "alternate_restriction_state": site["alternate_restriction_state"],
                         "alternate_entry_lead_m": float(target.get("alternate_entry_lead_m") or 60.0),
                         "camera_frames": {name: {"video_frame": index,
                             "source_kind": "diagnostic_fixture"} for name in VIEWS}})
            body_rows.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                              "body_vertices_m": body, "heading_deg": 0.0})
        packet = {"format": "route-motion-samples-v1", "source_kind": "diagnostic_fixture",
                  "diagnostic_fixture": True, "case_id": case_id,
                  "site_sha256": hashlib.sha256(site_text.encode()).hexdigest(),
                  "sampling_hz": 20, "frame_count": 9, "samples": rows}
        spec["files"]["original-site.json"] = site_text
        spec["files"]["original-route-motion.json"] = json.dumps(packet, sort_keys=True) + "\n"
        spec["files"]["body_history.jsonl"] = "\n".join(json.dumps(row) for row in body_rows) + "\n"
        spec["files"]["fixture-provenance.json"] = json.dumps({
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "source_kind": "synthetic_fixture"}) + "\n"
        manifest = json.loads(spec["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        spec["files"]["capture/manifest.json"] = json.dumps(manifest, sort_keys=True) + "\n"
        path = ROOT / ("diagnostic-" + tag + ".json")
        dump(path, spec)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": path.relative_to(REPO).as_posix(),
                               "sha256": sha(path)}],
                  "generator": {"source": path.relative_to(REPO).as_posix(),
                                "sha256": sha(path)}}
        dump(ROOT / ("diagnostic-" + tag + "-recipe.json"), recipe)


if __name__ == "__main__":
    main()
