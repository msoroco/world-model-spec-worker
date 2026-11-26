"""Author four exact, explicitly synthetic island compatibility recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXAMPLE = REPO / "runtime/fixtures/example.json"
REQUIREMENTS = (
    ("Qualifying rotary traffic island identity and original physical polygon",
     "NRS 484B.220(2) and frozen C130282 conditional witness", "island_passage",
     "measure_island_passage", "measured"),
    ("Original motor-vehicle body, heading, island-side samples and overlap",
     "NRS 484B.220(2) and original 20 Hz Native trace", "side_observation",
     "measure_side_observation", "measured"),
    ("Distinct connected inner and outer circulation lane sources",
     "frozen C130282 conditional witness and original route review", "lane_connectivity",
     "measure_lane_connectivity", "sourced_context"),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def body(x, y):
    return [[x + dx, y + dy, z] for z in (-.4, .4)
            for dx in (-.4, .4) for dy in (-.4, .4)]


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    plan["requirement_dispositions"] = [{"requirement": requirement, "source": source,
        "status": "selected_required", "evidence_or_gap": "No accepted original island recording; reviewed physical source and Native passage pending.",
        "case_ids": [case["case_id"] for case in plan["cases"]]}
        for requirement, source, _, _, _ in REQUIREMENTS]
    write(ROOT / "case-plan.json", plan)
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    road_hash = sha(example["files"]["road.xodr"].encode())
    for case in plan["cases"]:
        cid = case["case_id"]
        tag = cid.split("__")[-1]
        lane_role, side = tag.split("_")
        folder = ROOT / "cases" / tag
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        manifest = json.loads(files["capture/manifest.json"])
        manifest["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(manifest, sort_keys=True) + "\n"
        inner_id, outer_id = "10:-1", "10:-2"
        x = 2 if lane_role == "inner" else 3
        heading = [0, 1] if side == "right" else [0, -1]
        packet = {"case_id": cid, "layout": "multilane_roundabout",
            "native_map_sha256": road_hash, "map_sha256": road_hash,
            "map_name": "synthetic diagnostic map", "island": {
                "kind": "rotary_traffic_island", "identity_source": "synthetic diagnostic fixture only",
                "physical_polygon": [[-1,-1],[1,-1],[1,1],[-1,1]]},
            "circulation_surface_polygon": [[-4,-4],[4,-4],[4,4],[-4,4]],
            "circulation_lanes": [
                {"role": "inner", "lane_id": inner_id, "source_ref": "synthetic only", "route_source": "synthetic only"},
                {"role": "outer", "lane_id": outer_id, "source_ref": "synthetic only", "route_source": "synthetic only"}],
            "connected_route_source": "synthetic only", "vehicle_driver_source": "synthetic only",
            "selected_lane_role": lane_role, "requested_island_side": side,
            "entry_lane_id": "11:-1", "exit_lane_id": "12:-1",
            "route_source_sha256": road_hash, "ego_blueprint": "vehicle.diagnostic",
            "ego_spawn": {"x": x, "y": -3 if side == "right" else 3, "yaw": 90 if side == "right" else -90},
            "left_route_physical_review": side == "left",
            "ego_route": [
                {"x": x, "y": -3 if side == "right" else 3, "speed_mps": 3, "lane_id": "11:-1"},
                {"x": x, "y": -2 if side == "right" else 2, "speed_mps": 3,
                 "lane_id": inner_id if lane_role == "inner" else outer_id},
                {"x": x, "y": -1.5 if side == "right" else 1.5, "speed_mps": 3, "lane_id": "12:-1"}]}
        map_text = json.dumps(packet, sort_keys=True) + "\n"
        frame_map = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        rows = []
        for mapped in frame_map:
            center = [x, min(1, -1 + mapped["video_frame"] * .25)]
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                "ego_actor_id": 1, "ego_center": center, "ego_heading": heading,
                "ego_lane_id": inner_id if lane_role == "inner" else outer_id,
                "ego_vertices": body(*center), "ego_speed_mps": 3,
                "camera_frames": {}})
        trace_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        receipt = {"assignment_id": ROOT.name, "case_id": cid,
            "diagnostic_fixture": True, "fps": 20, "frame_count": len(rows),
            "map_sha256": sha(map_text.encode()), "trace_sha256": sha(trace_text.encode()),
            "camera_capture_complete": False, "camera_sources": {}}
        files["original-map.json"] = map_text
        files["original-trace.jsonl"] = trace_text
        files["original-receipt.json"] = json.dumps(receipt, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"scope":
            "CPU diagnostic only; synthetic island and route never establish original physical/legal acceptance",
            "case_id": cid, "frames": len(rows)}, sort_keys=True) + "\n"
        diagnostic_path = folder / "diagnostic.json"
        diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_path.write_text(json.dumps(diagnostic, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
        rel = diagnostic_path.relative_to(REPO).as_posix()
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": rel,
                         "sha256": sha(diagnostic_path.read_bytes())}],
            "generator": {"source": rel, "sha256": sha(diagnostic_path.read_bytes())}})
        write(folder / "measurement-contract.json", {"format": "worker-measurement-contract",
            "case_id": cid, "requirements": [
                {"disposition_index": index, "requirement": requirement, "source": source,
                 "output_key": key, "method": method, "value_type": "object", "kind": kind,
                 "inputs": ["original-map.json", "original-trace.jsonl", "original-receipt.json"]}
                for index, (requirement, source, key, method, kind) in enumerate(REQUIREMENTS)],
            "negative": {"remove": ["original-map.json"],
                         "error_contains": "Missing required source: original-map.json"}})


if __name__ == "__main__":
    build()
    print("four exact diagnostic recipes and selected measurement contracts")
