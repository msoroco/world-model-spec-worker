import hashlib
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_site_contract", Path(__file__).resolve().parents[1] / "native_site_contract.py")
site_contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_contract)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_runner


def write_bound(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class SiteTests(unittest.TestCase):
    def fixture(self, root, kind="stop_line"):
        site = {"native_map_name": "DiagnosticTown", "intersection_id": 6,
                "native_signal_id": 13, "other_native_signal_id": 14,
                "installed_uncovered_vehicular_heads": True,
                "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]],
                "entrance_road_lanes": [[1, -1], [2, -1]],
                "stop_line_exists": kind == "stop_line",
                "crosswalk_exists": kind == "crosswalk",
                "stop_boundary": {"kind": kind, "source": "map-and-original-front-view",
                                  "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]},
                "other_stop_line_exists": True, "other_crosswalk_exists": False,
                "other_stop_boundary": {"kind": "stop_line", "source": "other-approach-map-and-view",
                                        "point_xy_m": [0, 0], "upstream_normal_xy": [0, -1]},
                "approach_visibility_source": "native-map-and-front-view"}
        docs = {}
        for role, fields in site_contract.SOURCE_CLAIMS.items():
            document = {"format": "worker-inoperative-junction-source", "source_role": role,
                        "review_basis": "synthetic CPU fixture only",
                        "reviewed_site_fields": {field: site[field] for field in fields}}
            docs[role] = write_bound(root, role + ".json", document)
        review = {"format": "worker-inoperative-junction-review",
                  "review_status": "reviewed_candidate", "site": site, "source_documents": docs}
        config = {"site": site, "site_review": write_bound(root, "review.json", review)}
        return config

    def test_three_stopping_reference_branches(self):
        for kind in ("stop_line", "crosswalk", "nearest_view"):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = self.fixture(root, kind)
                receipt = site_contract.validate_site(config, root)
                self.assertEqual(receipt["selected_boundary"], kind)
                self.assertFalse(receipt["native_site_verified"])

    def test_rejects_tampered_source_and_unsourced_boundary_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            document = root / "signal_heads.json"
            document.write_text(document.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site"]["stop_line_exists"] = False
            with self.assertRaisesRegex(ValueError, "differs from bound review packet"):
                site_contract.validate_site(config, root)
            config = self.fixture(root)
            config["site_review"]["path"] = "../review.json"
            with self.assertRaisesRegex(ValueError, "escapes packet root"):
                site_contract.validate_site(config, root)

    def test_other_approach_boundary_must_be_sourced_and_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            self.assertEqual(config["site"]["other_stop_boundary"]["upstream_normal_xy"], [0, -1])
            config["site"]["other_stop_boundary"]["upstream_normal_xy"] = [-1, 0]
            with self.assertRaisesRegex(ValueError, "differs from bound review packet"):
                site_contract.validate_site(config, root)

    def test_two_actor_four_camera_capture_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.fixture(root)
            config.update(cell_id="C24757", law_id="NRS-484B-250-4",
                selected_case_id="testing__C24757__NRS-484B-250-4__motor_vehicle_driver__stop_line_other_prior",
                required_atoms=[], rate_hz=20, duration_s=40,
                physical_completion={"motion_source": "vehicle_signal_history.jsonl",
                                     "body_key": "ego.body_vertices_xy_m",
                                     "context_sources": ["junction_context.json"]},
                actor_routes={"ego": {"spawn": [1, -1, 10.0], "target_xy_m": [[-15, 0], [15, 0]],
                                       "release_frame": 50, "release_rule": "after_other_clear",
                                       "target_speed_mps": 4.0},
                              "other": {"spawn": [2, -1, 10.0], "target_xy_m": [[0, -15], [0, 15]],
                                        "release_frame": 30, "release_rule": "scheduled",
                                        "target_speed_mps": 4.0}},
                cameras=[{"name": name, "width": size[0], "height": size[1],
                          "fov_deg": 90, "pose": {"x": 0, "y": 0, "z": 10,
                                                 "yaw": 0, "pitch": -20}}
                         for name, size in native_runner.SIZES.items()])
            receipt = native_runner.validate_capture_plan(config, root)
            self.assertFalse(receipt["native_site_verified"])
            config["cameras"][2]["width"] = 640
            with self.assertRaisesRegex(ValueError, "dimensions"):
                native_runner.validate_capture_plan(config, root)
            config["cameras"][2]["width"] = 1280
            config["actor_routes"]["other"]["spawn"] = [1, -1, 10.0]
            with self.assertRaisesRegex(ValueError, "distinct Native approaches"):
                native_runner.validate_capture_plan(config, root)
            config["actor_routes"]["other"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["ego"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["other"]["spawn"] = [1, -1, 10.0]
            with self.assertRaisesRegex(ValueError, "ordered signal-governed"):
                native_runner.validate_capture_plan(config, root)
            config["actor_routes"]["ego"]["spawn"] = [1, -1, 10.0]
            config["actor_routes"]["other"]["spawn"] = [2, -1, 10.0]
            config["actor_routes"]["other"]["release_rule"] = "after_other_clear"
            with self.assertRaisesRegex(ValueError, "Circular Native release"):
                native_runner.validate_capture_plan(config, root)


if __name__ == "__main__":
    unittest.main()
