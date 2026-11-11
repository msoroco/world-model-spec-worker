import sys
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from runner import CASE, validate_config, _sensor_frame
from camera_setup import SIZES
from queue import Queue


def config():
    site = {"native_map_name": "FixtureTown", "crossing_id": 7,
            "ego_highway_id": 1, "other_highway_id": 2,
            "crossing_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
            "same_statutory_crossing_reviewed": True,
            "ego_approach": [-10,0,0,0], "ego_entry": [-4,0,0,0],
            "other_approach": [0,-10,0,90], "other_entry": [0,-4,0,90],
            "routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                       "other": [[0,-10],[0,-4],[0,0],[0,10]]},
            "cameras": {name: [0,0,10,0,0,0] for name in SIZES}}
    for key in ("polygon_source", "entrance_source", "median_spacing_source",
                "device_review_source", "statutory_crossing_review_source",
                "approach_geometry_source"):
        site[key] = "synthetic/" + key
    return {"selected_case_id": CASE, "law_id": "NRS-484B-250-2",
            "cell_id": "C125714", "duration_s": 55, "rate_hz": 20,
            "required_atoms": [], "recording_description": {},
            "physical_completion": {"body_key": "ego_vertices_m",
                                    "context_sources": ["road_geometry.json"]},
            "ego_target_speed_mps": 5, "other_target_speed_mps": 5,
            "other_release_frame": 20, "site": site}


class RunnerTests(unittest.TestCase):
    def test_cpu_config_requires_hashed_site_review(self):
        with self.assertRaisesRegex(ValueError, "Hashed site review packet"):
            validate_config(config())

    def test_routes_and_camera_plan_reach_review_gate(self):
        with patch("runner.verify_site_packet", return_value={}) as reviewed:
            value = validate_config(config())
        self.assertEqual(value["selected_case_id"], CASE)
        reviewed.assert_called_once()

    def test_synthetic_hashed_site_packet_passes_cpu_review(self):
        value = config()
        site = value["site"]
        site["selected_roadway_index"] = 0
        documents = {
            "polygon_source": {"source": "synthetic crossing polygon"},
            "entrance_source": {"source": "synthetic entrance inventory"},
            "median_spacing_source": {
                "format": "worker-median-roadway-geometry", "units": "m",
                "source_description": "synthetic two-roadway CPU fixture",
                "roadway_polygons_xy_m": [
                    [[-5,-5],[5,-5],[5,5],[-5,5]],
                    [[-5,6],[5,6],[5,16],[-5,16]]]},
            "device_review_source": {
                "format": "worker-median-device-inventory",
                "crossing_id": 7, "native_map_name": "FixtureTown",
                "all_entrances_reviewed": True,
                "review_basis": "synthetic complete entrance fixture",
                "entrances": [{"road_id": 11, "lane_id": -1, "highway_id": 1},
                              {"road_id": 22, "lane_id": -1, "highway_id": 2}],
                "devices": []},
            "statutory_crossing_review_source": {"source": "synthetic test claim"},
            "approach_geometry_source": {"source": "synthetic test waypoints"},
        }
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            sources = {}
            for key, body in documents.items():
                path = root / (key + ".json")
                path.write_text(json.dumps(body))
                sources[key] = {"path": path.name,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                site[key] = path.name
            packet = root / "site-review.json"
            packet.write_text(json.dumps({"format": "worker-median-site-review",
                                          "review_status": "reviewed_candidate",
                                          "site": site, "source_documents": sources}))
            value["site_review"] = {"path": packet.name,
                                    "sha256": hashlib.sha256(packet.read_bytes()).hexdigest()}
            self.assertEqual(validate_config(value, root)["selected_case_id"], CASE)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(value))
            completed = subprocess.run([sys.executable, str(PACKAGE / "runner.py"),
                                        "--config", str(config_path), "--check"],
                                       capture_output=True, text=True, check=True)
            self.assertFalse(json.loads(completed.stdout)["carla_started"])
            packet.write_text(packet.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                validate_config(value, root)

    def test_bad_route_and_skipped_camera_frame_rejected(self):
        value = config()
        value["site"]["routes"]["other"][-1] = [0, -2]
        with self.assertRaisesRegex(ValueError, "route has no exit"):
            validate_config(value)
        queue = Queue()
        queue.put(type("Image", (), {"frame": 12})())
        with self.assertRaisesRegex(ValueError, "skipped requested frame"):
            _sensor_frame(queue, 11)


if __name__ == "__main__":
    unittest.main()
