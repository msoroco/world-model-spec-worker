"""Name the executable acquisition and saved evidence for each law channel."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EVIDENCE = {
    "official steady red alone": "trace.jsonl native_frame.signal_actor_id/signal_state",
    "antecedent stop location": "trace.jsonl distance_to_stop_boundary_m and native_frame.ego.body_vertices_xyz_m",
    "complete stop": "trace.jsonl native_frame.ego.velocity_xyz_mps with site.json stop_boundary",
    "extreme left of one-way approach": "site.json approach lane_centers_xy and trace.jsonl selected_approach_lane_id",
    "receiving one-way to left": "site.json receiving.direction_xy/one_way_to_left and trace.jsonl junction_exited",
    "pedestrian right-of-way": "trace.jsonl native_frame.pedestrians and pedestrian_conflict",
    "other traffic right-of-way": "trace.jsonl native_frame.other_traffic and traffic_conflict",
    "yield response": "trace.jsonl control_request, pedestrian_conflict and traffic_conflict",
}


def main() -> None:
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        construction = json.loads((ROOT / entry["construction"]).read_text())
        channels = {item["name"] for item in construction["recording_description"]["channels"]}
        if channels != set(EVIDENCE):
            raise ValueError("recording channels differ from acquisition inventory")
        entry["acquisition"] = {name: {
            "entrypoint": "native_capture.py",
            "method": "original Native frame acquisition joined to reviewed site and saved analysis",
            "evidence": EVIDENCE[name],
        } for name in sorted(channels)}
        entry["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT",
        }
        print("bound Native acquisition inventory", entry["case_id"].rsplit("__", 1)[-1])
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
