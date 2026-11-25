"""Generate six explicitly synthetic, case-specific compatibility input recipes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXAMPLE = REPO / "runtime/fixtures/example.json"
REQUIREMENTS = (
    ("Original multilane roundabout entry lane and connected circulating lane",
     "frozen C130864 conditional witness and original map review",
     "lane_connectivity", "measure_lane_connectivity"),
    ("Original entering operator and sampled entry or wait motion",
     "LVMC 11.43.010(B) and original vehicle trace",
     "roundabout_entry", "measure_roundabout_entry"),
    ("Another motor vehicle already circulating in an identified lane",
     "frozen C130864 conditional witness and original opponent route",
     "circulating_presence", "measure_circulating_presence"),
    ("Observed pre-entry traffic spacing and potential conflict without legal cutoff",
     "LVMC 11.43.010(B) and original body histories",
     "gap_observation", "measure_gap_observation"),
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


def _body(x, y):
    return [[x + dx, y + dy, z] for z in (-.5, .5)
            for dx in (-.5, .5) for dy in (-.5, .5)]


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    plan["requirement_dispositions"] = [{"requirement": requirement,
        "source": source, "status": "selected_required",
        "evidence_or_gap": "No accepted original recording; source-reviewed map and physical trace remain pending.",
        "case_ids": [case["case_id"] for case in plan["cases"]]}
        for requirement, source, _, _ in REQUIREMENTS]
    _text(ROOT / "case-plan.json", plan)
    example = json.loads(EXAMPLE.read_text())
    road_hash = _sha(example["files"]["road.xodr"].encode())
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = ROOT / "cases" / short
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        source_manifest = json.loads(files["capture/manifest.json"])
        source_manifest["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(source_manifest, sort_keys=True) + "\n"
        adjacent = case["opponent_lane_relation"] == "adjacent"
        wider = case["planned_gap_condition"] == "wider"
        wait = case["ego_entry_request"] == "wait"
        other_x, other_y = (3 if wider else 1), (1 if adjacent else 0)
        packet = {"case_id": cid, "layout": "multilane_roundabout",
            "map_sha256": road_hash,
            "jurisdiction_source": "synthetic diagnostic context only",
            "roundabout_geometry_source": "synthetic diagnostic geometry only",
            "circulating_surface_polygon": [[-4, -4], [4, -4], [4, 4], [-4, 4]],
            "entry_conflict_polygon": [[-2, -4], [2, -4], [2, 0], [-2, 0]],
            "circulating_lanes": [{"lane_id": "outer"}, {"lane_id": "inner"}],
            "ego_entry_lane": {"lane_id": "entry-1",
                               "connected_circulating_lane_id": "outer"},
            "opponent_route": {"circulating_lane_id": "inner" if adjacent else "outer",
                "route_source": "synthetic diagnostic route only",
                "potential_conflict_source": "synthetic diagnostic geometry only",
                "initial_position": [other_x, other_y]},
            "entry_line": [[-2, -4], [2, -4]],
            "map_name": "synthetic diagnostic map",
            "ego_blueprint": "vehicle.ego", "opponent_blueprint": "vehicle.other",
            "ego_spawn": {"x": 0, "y": -5},
            "opponent_spawn": {"x": other_x, "y": other_y},
            "ego_release_tick": 700 if wait else 20,
            "opponent_release_tick": 0,
            "ego_route": [{"x": 0, "y": -5, "speed_mps": 3, "lane_id": "entry-1"},
                          {"x": 0, "y": -3, "speed_mps": 3, "lane_id": "entry-1"},
                          {"x": 0, "y": -1, "speed_mps": 3, "lane_id": "outer"}],
            "opponent_points": [{"x": other_x, "y": other_y,
                                  "speed_mps": 4, "lane_id": "inner" if adjacent else "outer"},
                                 {"x": other_x + 1, "y": other_y,
                                  "speed_mps": 4, "lane_id": "inner" if adjacent else "outer"},
                                 {"x": other_x + 2, "y": other_y,
                                  "speed_mps": 4, "lane_id": "inner" if adjacent else "outer"}]}
        map_text = json.dumps(packet, sort_keys=True) + "\n"
        frames = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        rows = []
        for index, mapped in enumerate(frames):
            y = -5 if wait else min(3, -5 + index)
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                "ego_vertices": _body(0, y), "opponent_vertices": _body(other_x, other_y),
                "ego_speed_mps": 0 if wait else 3, "opponent_speed_mps": 4})
        trace_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        receipt = {"assignment_id": ROOT.name, "case_id": cid,
            "diagnostic_fixture": True, "fps": 20, "frame_count": len(rows),
            "map_sha256": _sha(map_text.encode()),
            "trace_sha256": _sha(trace_text.encode()),
            "camera_capture_complete": False, "camera_sources": {}}
        files["original-map.json"] = map_text
        files["original-trace.jsonl"] = trace_text
        files["original-receipt.json"] = json.dumps(receipt, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"scope":
            "CPU diagnostic only: synthetic roundabout geometry, body traces and video; not original site evidence",
            "case_id": cid, "frames": len(rows)}, sort_keys=True) + "\n"
        generator = folder / "diagnostic.json"
        _text(generator, diagnostic)
        _text(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json",
                "source": str(generator.relative_to(REPO)),
                "sha256": _sha(generator.read_bytes())}],
            "generator": {"source": str(generator.relative_to(REPO)),
                "sha256": _sha(generator.read_bytes())}})
        contract = {"format": "worker-measurement-contract", "case_id": cid,
            "requirements": [{"disposition_index": index,
                "requirement": requirement, "source": source,
                "output_key": key, "method": method, "value_type": "object",
                "kind": "measured" if key != "lane_connectivity" else "sourced_context",
                "inputs": ["original-map.json", "original-trace.jsonl",
                           "original-receipt.json"]}
                for index, (requirement, source, key, method) in enumerate(REQUIREMENTS)],
            "negative": {"remove": ["original-map.json"],
                         "error_contains": "Missing required source: original-map.json"}}
        _text(folder / "measurement-contract.json", contract)


if __name__ == "__main__":
    build()
    print("six synthetic diagnostic recipes and selected measurement contracts authored")
