import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from runner import TARGETS, _camera_frame, capture, validate_config
from site_packet import source_bindings
from camera_setup import SIZES


def config(case):
    site = {"native_map_name": "FixtureTown", "crossing_id": 7,
            "ego_highway_id": 1, "other_highway_id": 2,
            "crossing_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
            "ego_approach": [-10,0,0,0], "ego_entry": [-4,0,0,0],
            "other_approach": [0,-10,0,90], "other_entry": [0,-4,0,90],
            "routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                       "other": [[0,-10],[0,-4],[0,0],[0,10]]},
            "cameras": {name: [0,0,10,0,0,0] for name in SIZES},
            "expected_approach_lanes": {"ego": [11,-1], "other": [22,-1]},
            "head_geometry_sources": {"ego": "ego_head_geometry.json",
                                      "other": "other_head_geometry.json"},
            "selected_stop_references": {
                "ego": {"kind": "marked_stop_line", "segment_xy_m": [[-5,-2],[-5,2]],
                        "geometry_source": "ego_stop_geometry.json", "reference_review_source": "ego_stop_review.json"},
                "other": {"kind": "marked_stop_line", "segment_xy_m": [[-2,-5],[2,-5]],
                          "geometry_source": "other_stop_geometry.json", "reference_review_source": "other_stop_review.json"}}}
    for key in ("polygon_source", "approach_geometry_source", "device_inventory_source", "camera_plan_source"):
        site[key] = key + ".json"
    return {"selected_case_id": case, "law_id": "NRS-484B-250-2", "cell_id": "C125751",
            "duration_s": 55, "rate_hz": 20, "target_signal_state": TARGETS[case][0],
            "required_atoms": [], "recording_description": {},
            "ego_target_speed_mps": 5, "other_target_speed_mps": 5,
            "other_release_frame": 20, "site": site}


def write_packet(root, value):
    site = value["site"]
    documents = {}
    for kind, name in source_bindings(site).items():
        if kind == "polygon":
            content = {"polygon_xy_m": site["crossing_polygon_xy_m"]}
        elif kind == "approaches":
            content = {"approach_poses": {role: site[role + "_approach"] for role in ("ego", "other")}}
        elif kind == "device_inventory":
            content = {"governed_road_lanes": site["expected_approach_lanes"],
                       "all_entrances_reviewed": True}
        elif kind == "cameras":
            content = {"camera_poses": site["cameras"]}
        elif kind.endswith("_stop_geometry"):
            content = {"segment_xy_m": site["selected_stop_references"][kind.split("_")[0]]["segment_xy_m"]}
        elif kind.endswith("_stop_review"):
            ref = site["selected_stop_references"][kind.split("_")[0]]
            content = {"selected_kind": ref["kind"], "segment_xy_m": ref["segment_xy_m"]}
        else:
            role = kind.split("_")[0]
            content = {"governed_road_lane": site["expected_approach_lanes"][role],
                       "head_world_location_xyz_m": [-5,0,4] if role == "ego" else [0,-5,4],
                       "planned_camera": "approach" if role == "ego" else "reference_corner"}
        body = {"format": "worker-c125751-site-source", "source_kind": kind,
                "native_map_name": site["native_map_name"], "crossing_id": site["crossing_id"],
                "review_basis": "synthetic CPU site fixture; no physical acceptance",
                "diagnostic_only": True, "content": content}
        path = root / name
        path.write_text(json.dumps(body, indent=2) + "\n")
        documents[kind] = {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    packet = root / "site-review.json"
    packet.write_text(json.dumps({"format": "worker-c125751-two-signal-site-review",
                                  "review_status": "candidate_reviewed", "site": site,
                                  "source_documents": documents}, indent=2) + "\n")
    value["site_review"] = {"path": packet.name, "sha256": hashlib.sha256(packet.read_bytes()).hexdigest()}
    return packet


class RunnerTests(unittest.TestCase):
    def test_both_exact_cases_cpu_check_without_carla(self):
        for case in TARGETS:
            with tempfile.TemporaryDirectory() as temp:
                value = config(case)
                write_packet(Path(temp), value)
                validate_config(value, Path(temp))
                path = Path(temp) / "config.json"
                path.write_text(json.dumps(value))
                completed = subprocess.run([sys.executable, str(PACKAGE / "runner.py"),
                                            "--config", str(path), "--check"],
                                           capture_output=True, text=True, check=True)
                receipt = json.loads(completed.stdout)
                self.assertEqual(tuple(receipt["signal_states"]), TARGETS[case])
                self.assertEqual(receipt["frames"], 1100)
                self.assertFalse(receipt["carla_started"])
                default_check = subprocess.run([sys.executable, str(PACKAGE / "runner.py"), "--check"],
                                               cwd=temp, capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(default_check.stdout)["case_id"], case)

    def test_bad_route_and_skipped_camera_frame_rejected(self):
        case = next(iter(TARGETS))
        value = config(case)
        value["site"]["routes"]["other"][-1] = [0,-2]
        with self.assertRaisesRegex(ValueError, "route has no exit"):
            validate_config(value)
        queue = Queue()
        queue.put(type("Image", (), {"frame": 12})())
        with self.assertRaisesRegex(ValueError, "skipped requested frame"):
            _camera_frame(queue, 11)

    def test_synthetic_site_and_wrong_case_pair_rejected(self):
        case = next(iter(TARGETS))
        value = config(case)
        value["site"]["diagnostic_site_only"] = True
        with self.assertRaisesRegex(ValueError, "Synthetic diagnostic site"):
            validate_config(value)
        value = config(case)
        value["target_signal_state"] = "Off"
        with self.assertRaisesRegex(ValueError, "requested ego Native state"):
            validate_config(value)

    def test_site_source_hash_and_content_bound_to_plan(self):
        case = next(iter(TARGETS))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            value = config(case)
            write_packet(root, value)
            validate_config(value, root)
            source = root / value["site"]["device_inventory_source"]
            body = json.loads(source.read_text())
            body["content"]["governed_road_lanes"]["other"] = [99,-1]
            source.write_text(json.dumps(body))
            with self.assertRaisesRegex(ValueError, "source missing or changed: device_inventory"):
                validate_config(value, root)
            packet_path = root / value["site_review"]["path"]
            packet = json.loads(packet_path.read_text())
            packet["source_documents"]["device_inventory"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(packet))
            value["site_review"]["sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "content differs from selected geometry: device_inventory"):
                validate_config(value, root)

    def test_diagnostic_packet_cannot_enter_native_capture(self):
        case = next(iter(TARGETS))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            value = config(case)
            write_packet(root, value)
            output = root / "attempt"
            output.mkdir()
            (output / "construction.json").write_text("{}\n")
            args = NS(output_dir=str(output), config=str(root / "config.json"))
            with self.assertRaisesRegex(ValueError, "Diagnostic site sources"):
                capture(args, value)


if __name__ == "__main__":
    unittest.main()
