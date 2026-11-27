"""Build exact source-gated NRS 484B.223(3)(b) Native bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ("short_travel", "boundary_travel", "long_travel", "onto_highway_contrast")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
SOURCES = ("runner.py", "native_live.py", "native_operator.py", "native_capture.py",
           "native_output_bridge.py", "center_lane_site.py", "center_lane_geometry.py",
           "center_lane_distance_probe.py",
           "analysis.py", "case-plan.json")
CHANNELS = ("reviewed_highway_design", "original_body_lane_occupancy",
            "original_center_lane_distance", "original_route_and_maneuver",
            "original_four_camera_pixels")
TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner

class BundleTests(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        selected = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())["selected_case_id"]
        self.assertEqual(runner.check()["selected_case_id"], selected)
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed center-lane"):
                    runner.main()
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    exact = {AID + "__" + kind for kind in KINDS}
    if {row["case_id"] for row in plan["cases"]} != exact:
        raise ValueError("four exact planned center-lane cases changed")
    source = {name: (HERE / name).read_text() for name in SOURCES}
    source["tests/test_bundle.py"] = TEST
    entries = []
    for kind in KINDS:
        case_id = AID + "__" + kind
        description = {
            "channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                          "method": "original Native source-sealed lane, body, route and RGB readback",
                          "time_window": "all 900 original ticks",
                          "reference_frame": "original loaded CARLA map/world",
                          "uncertainty": "200-foot boundary interpolation and physical realization unresolved"}
                         for name in CHANNELS],
            "context_inputs": [{"name": "reviewed_center_lane_site", "unit": "source",
                                "method": "hash-bound highway designation, Native lane topology and junction review"}],
            "limitations": ["Original body entry and exit interpolation needs review.",
                            "Observed distance does not itself decide legal compliance."]}
        config = {"assignment_id": AID, "law_id": "NRS-484B-223-3b",
                  "cell_id": "C382162", "actor": "motor_vehicle_driver",
                  "selected_case_id": case_id, "supported_case_ids": sorted(exact),
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "rate_hz": 20, "duration_s": 45, "frame_count": 900,
                  "required_atoms": [], "source_packets": [],
                  "cameras": [{"name": view, "width": width, "height": height,
                               "fov_deg": 80, "pose_strategy": "source-reviewed lane and turn geometry"}
                              for view, width, height in CAMERAS],
                  "case": {"case_id": case_id, "recording_description": description}}
        for candidate, speed in (("primary", 5.0), ("fallback1", 3.5)):
            selected = dict(config, controller_target_speed_mps=speed)
            files = dict(source)
            files["config.json"] = json.dumps(selected, sort_keys=True, indent=2) + "\n"
            construction = {
                "law_id": "NRS-484B-223-3b", "cell_id": "C382162",
                "actor": "motor_vehicle_driver", "case_id": case_id,
                "entrypoint": "runner.py", "recording_description": description,
                "measurement_plan": {"case_id": case_id,
                                     "source_packets": ["native/site.json", "native/history.json",
                                                        "native/frame-map.json", "road.xodr"],
                                     "procedure": "analysis.py", "legal_judgment": "unresolved"},
                "static_checks": ["reviewed original OpenDRIVE, exclusive bidirectional lane and highway status",
                                  "reviewed center-lane polygon, eight-vertex body and original lane/road/turn readbacks",
                                  "900 original 20 Hz synchronized frames and four RGB views"],
                "termination_rules": ["900 original Native ticks", "route completion observed separately"],
                "mechanisms": ["source-gated lane topology, highway and center-lane polygon",
                               "lazy Native vehicle route controller",
                               "four source-hashed original RGB callbacks"],
                "files": [{"path": name, "content": value} for name, value in files.items()]}
            relative = Path("cases") / kind / ("construction.json" if candidate == "primary"
                                                else "fallback1/construction.json")
            path = HERE / relative
            write(path, construction)
            if kind == KINDS[0] and candidate == "primary":
                write(HERE / "config.json", selected)
                write(HERE / "construction.json", construction)
            if candidate == "primary":
                entries.append({"case_id": case_id, "kind": "delivery",
                                "construction": str(relative), "construction_sha256": sha(path),
                                "candidate_risk": {"status": "physical",
                                                   "reason": "The reviewed center-lane extent or controlled route may not realize the planned 190/200/210-foot traversal and synchronized departure views."},
                                "measurement_procedure": {"entrypoint": "analysis.py",
                                                          "method": "saved original body, lane, distance and departure measurement"},
                                "acquisition": {name: {"entrypoint": "analysis.py",
                                                       "method": "source-hashed original Native body/lane/route or RGB readback",
                                                       "evidence": "channels/" + name + ".jsonl"}
                                                for name in CHANNELS},
                                "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                                "candidates": []})
            else:
                entries[-1]["candidates"].append({
                    "id": "fallback1", "construction": str(relative),
                    "construction_sha256": sha(path),
                    "changed_knobs": ["engineering controller speed 3.5 m/s rather than 5.0 m/s"],
                    "trigger": {"source": "original Native lane and frame-map history",
                                "metric": "center-lane occupancy with synchronized junction coverage",
                                "failure_condition": "primary misses actual governed lane or view due to route overshoot"}})
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
