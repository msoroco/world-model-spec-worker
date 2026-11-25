import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("saved_encounter", ROOT / "saved_encounter.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CASE = ROOT.name + "__bicycle_brake"


def waypoint(x, y, junction=None):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "original-map#waypoint"}


def write_json(root, name, data):
    path = root / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def attempt(root):
    site = {"map_sha256": "a" * 64, "map_source_ref": "original-map", "junction_id": 7,
            "ego_route": [waypoint(-20, 0), waypoint(0, 0, 7), waypoint(20, 0)],
            "rider_route": [waypoint(0, -20), waypoint(0, 0, 7), waypoint(0, 20)],
            "motor_vehicle": {"source_ref": "original-blueprint#ego", "blueprint_id": "vehicle.sedan",
                              "rail_bound": False},
            "rider": {"source_ref": "original-blueprint#rider", "blueprint_id": "vehicle.bicycle",
                      "person_actor_id": 42, "kind": "bicycle", "moped": False, "motorized": False,
                      "wheel_diameters_in": [26, 26]}}
    rows = [{"source": "original_native", "case_id": CASE, "map_sha256": "a" * 64,
             "frame": n + 100, "time_s": n * 0.05, "ego_actor_id": 1, "rider_actor_id": 2,
             "rider_person_actor_id": 42,
             "rider_kind_observed": "bicycle", "rider_mounted_observed": True,
             "surface_gap_m": 3.0, "ego_speed_mps": 8.0, "rider_speed_mps": 3.0,
             "ego_brake_observed": 0.7, "conflict_window_observed": n in range(300, 400),
             "contact_observed": False} for n in range(900)]
    cameras = {name: [row["frame"] for row in rows] for name in MODULE.CAMERAS}
    packet = {"case_id": CASE, "source": "original_native", "hz": 20,
              "site": write_json(root, "site.json", site),
              "history": write_json(root, "history.json", rows),
              "camera_frames": write_json(root, "camera-frames.json", cameras)}
    write_json(root, "encounter-packet.json", packet)
    return packet, site, rows, cameras


class SavedEncounterTests(unittest.TestCase):
    def test_source_bound_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            attempt(root)
            result = MODULE.finalize_saved(root)
            self.assertEqual(result["original_frames"], 900)
            self.assertEqual(set(result["camera_frames"]), set(MODULE.CAMERAS))
            self.assertEqual(result["measurement"]["response"], "brake")
            self.assertEqual(result["legal_judgment"], "unresolved")
            self.assertFalse(result["actual_pixels"])

    def test_tampered_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            attempt(root)
            (root / "history.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash drift"):
                MODULE.finalize_saved(root)

    def test_resealed_changed_rider_person_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            packet, _, rows, _ = attempt(root)
            rows[320]["rider_person_actor_id"] = 99
            packet["history"] = write_json(root, "history.json", rows)
            write_json(root, "encounter-packet.json", packet)
            with self.assertRaisesRegex(ValueError, "rider person identity"):
                MODULE.finalize_saved(root)

    def test_missing_camera_and_frame_drift_rejected(self):
        for defect in ("missing", "drift"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                packet, _, _, cameras = attempt(root)
                if defect == "missing":
                    del cameras["reference_corner"]
                else:
                    cameras["reference_corner"][300] += 1
                packet["camera_frames"] = write_json(root, "camera-frames.json", cameras)
                write_json(root, "encounter-packet.json", packet)
                with self.assertRaisesRegex(ValueError, "camera"):
                    MODULE.finalize_saved(root)

    def test_wrong_case_and_requested_history_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            packet, _, rows, _ = attempt(root)
            packet["case_id"] = ROOT.name + "__bicycle_maintain"
            write_json(root, "encounter-packet.json", packet)
            with self.assertRaisesRegex(ValueError, "case drift"):
                MODULE.finalize_saved(root)
            packet["case_id"] = CASE
            rows[320]["source"] = "scripted_request"
            packet["history"] = write_json(root, "history.json", rows)
            write_json(root, "encounter-packet.json", packet)
            with self.assertRaisesRegex(ValueError, "original"):
                MODULE.finalize_saved(root)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            packet, _, _, _ = attempt(root)
            packet["history"]["path"] = "../history.json"
            write_json(root, "encounter-packet.json", packet)
            with self.assertRaisesRegex(ValueError, "escapes"):
                MODULE.finalize_saved(root)


if __name__ == "__main__":
    unittest.main()
