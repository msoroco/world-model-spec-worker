"""Author case-specific synthetic source fixtures for pinned CPU compatibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    video_map = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    if len(video_map) != 9:
        raise ValueError("pinned small media fixture changed")
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        target = case.get("target", {})
        speed = target.get("ego_speed_mps", 5.0)
        edge = target.get("paved_right_edge_m", 3.5 if suffix == "slow_center_narrow" else 4.7)
        right_offset = target.get("ego_path_offset_m", 1.1 if suffix == "slow_right_wide" else 0.0)
        station = 60 if suffix == "slow_center_obstruction_near" else 85
        immediate = suffix != "slow_center_no_follower"
        site = {"case_id": case_id, "site_ref_sha256": _sha(REPO / "inputs" / ROOT.name / "assignment.json"),
                "cpu_test_synthetic_only": True,
                "nrs_484b_630_context_source": "Frozen 627(1)(a) cross-reference only; no legal applicability finding",
                "requested_values": {"ego_speed_mps": speed,
                                     "paved_right_edge_m": edge,
                                     "ego_path_offset_m": right_offset,
                                     "obstruction_station_m": station}}
        site_text = json.dumps(site, sort_keys=True) + "\n"
        frames = [{"frame": i, "time_s": frame["time_s"],
                   "camera_frames": {name: frame["carla_frame"] for name in
                       ("overview", "approach", "reference_corner", "driver_reference")}}
                  for i, frame in enumerate(video_map)]
        frame_map = {"source_kind": "original_native_frame_map", "case_id": case_id,
                     "frames": frames}
        frame_text = json.dumps(frame_map, sort_keys=True) + "\n"
        rows = []
        for i, frame in enumerate(video_map):
            rows.append({"frame": i, "time_s": frame["time_s"],
                "ego_actor_id": 10, "follower_actor_id": 11,
                "ego_lane_id": "-1", "follower_lane_id": "-1" if immediate else "1",
                "opposite_lane_id": "1", "one_lane_each_direction_readback": True,
                "paved_right_edge_m": edge, "highway_right_edge_m": edge + 0.5,
                "obstruction_left_edge_m": 4.0, "obstruction_right_edge_m": 4.4,
                "ego_body_left_edge_m": right_offset - 0.9,
                "ego_body_right_edge_m": right_offset + 0.9,
                "ego_speed_mps": speed, "follower_speed_mps": 8.0,
                "follower_along_route_body_gap_m": 20.0,
                "obstruction_station_m": station,
                "ego_station_m": 45.0 + i * speed / 20,
                "follower_station_m": 20.0 + i * 8 / 20})
        motion = {"assignment_id": ROOT.name, "case_id": case_id,
                  "original_trace_id": "synthetic-compatibility-only",
                  "source_kind": "diagnostic_fixture",
                  "original_frame_map_sha256": hashlib.sha256(frame_text.encode()).hexdigest(),
                  "frames": rows}
        relation = {"case_id": case_id, "source_kind": "original_native_relation",
                    "relation_basis_source": "synthetic CPU fixture, never physical evidence",
                    "samples": [{"frame": i, "time_s": frame["time_s"],
                                 "follower_actor_id": 11, "immediately_behind": immediate}
                                for i, frame in enumerate(video_map)]}
        spec = json.loads(json.dumps(base))
        spec["files"].update({
            "original-site.json": site_text,
            "original-frame-map.json": frame_text,
            "original-motion.json": json.dumps(motion, sort_keys=True) + "\n",
            "original-relation.json": json.dumps(relation, sort_keys=True) + "\n",
            "fixture-provenance.json": json.dumps({"diagnostic_fixture": True,
                "physical_acceptance_claimed": False, "case_id": case_id,
                "scope": "Synthetic CPU source and media compatibility only; no physical or legal finding."}) + "\n",
        })
        path = ROOT / ("diagnostic-" + suffix + ".json")
        path.write_text(json.dumps(spec, separators=(",", ":")) + "\n", encoding="utf-8")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic specification exceeds return file limit")
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": f"work/{ROOT.name}/{path.name}", "sha256": _sha(path)},
                  "sources": [{"path": "diagnostic-input.json",
                               "source": f"work/{ROOT.name}/{path.name}",
                               "sha256": _sha(path)}]}
        (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            json.dumps(recipe, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
