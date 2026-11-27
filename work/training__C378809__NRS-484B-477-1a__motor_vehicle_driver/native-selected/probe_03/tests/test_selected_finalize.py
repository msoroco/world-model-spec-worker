import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selected_finalize", ROOT / "selected_finalize.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from selected_plan import ASSIGNMENT, CELL, SOURCE_KEYS


def write(path, value):
    path.write_text(json.dumps(value) + "\n")


class SavedReducerTest(unittest.TestCase):
    def make_diagnostic(self, root):
        case = ASSIGNMENT + "__probe_01"
        survey = {key: "diagnostic:" + key for key in SOURCE_KEYS}
        survey.update(source_kind="original_native_alley_survey", fixed_cell=CELL,
                      ordinance_status="unknown", reviewer="diagnostic-surveyor",
                      reviewed_source_sha256="diagnostic-survey-hash",
                      spawn_xyz_yaw_deg=[0, 0, 0, 0], park_xyz_m=[1, 0, 0],
                      goods_origin_xyz_m=[1, 1, 0],
                      goods_destination_xyz_m=[2, 1, 0],
                      vehicle_blueprint="vehicle.diagnostic",
                      goods_blueprint="static.prop.diagnostic")
        write(root / "site-survey.json", survey)
        videos = {}
        for view in module.VIEWS:
            path = root / (view + ".mkv")
            path.write_bytes(("diagnostic-stand-in:" + view).encode())
            videos[view] = module.sha(path)
        write(root / "goods-review.json", {
            "source_kind": "independent_original_video_review", "case_id": case,
            "reviewer": "diagnostic-reviewer", "full_interval_reviewed": True,
            "video_sha256": videos, "observed_event_ids": ["diagnostic-goods-event"],
            "observed_event_frames": {"diagnostic-goods-event": 300},
            "observed_door_open_frame_ids": [],
            "commercial_classification_source_id": "diagnostic-class-review",
            "commercial_classification_observed": False,
            "vehicle_within_alley_frame_ids": list(range(600))})
        with (root / "alley-native.jsonl").open("w") as trace, \
                (root / "video_frames.jsonl").open("w") as frame_map:
            for index in range(600):
                trace.write(json.dumps({"source_kind": "original_native_observation",
                    "case_id": case, "frame": index, "native_frame": index + 20,
                    "t_s": index / 20, "vehicle_id": 7,
                    "alley_boundary_source_id": survey["alley_boundary_source_id"],
                    "position_xyz_m": [1, 0, 0], "velocity_xyz_mps": [0, 0, 0]}) + "\n")
                frame_map.write(json.dumps({"video_frame": index,
                    "native_frame": index + 20, "time_s": index / 20}) + "\n")
        return case

    def test_diagnostic_stand_in_joins(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            result = module.reduce_saved(root, case)
            self.assertEqual(result["stopped_in_alley_frames"], 600)
            self.assertEqual(result["observed_goods_event_ids"],
                             ["diagnostic-goods-event"])
            self.assertIsNone(result["expeditiousness"])
            self.assertFalse(result["physical_completion"])

    def test_canonical_saved_outputs_from_diagnostic_stand_in(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            write(root / "config.json", {"selected_case_id": case})
            write(root / "construction.json", {"recording_description": {
                "channels": [{"name": name, "unit": "source observation"}
                             for name in ("kin.position", "kin.speed", "st.alley", "drv.standing_or_parked",
                                          "kin.time", "kin.extent", "sig.door_open",
                                          "ru.commercial_motor_vehicle",
                                          "st.driveway_or_alley_entrance", "rel.occupies")]}})
            report = module.finalize(root, root / "analysis-report.json")
            self.assertEqual(report["case_id"], case)
            self.assertEqual(len(list((root / "channels").glob("*.jsonl"))), 10)
            native = json.loads((root / "result.json").read_text())
            self.assertFalse(native["accepted"])
            self.assertFalse(native["setup_confirmed"])

    def test_missing_goods_review_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            (root / "goods-review.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                module.reduce_saved(root, case)

    def test_changed_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            path = root / "video_frames.jsonl"
            rows = path.read_text().splitlines()
            rows[1] = json.dumps({"video_frame": 1, "native_frame": 999, "time_s": .05})
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(ValueError, "frame join changed"):
                module.reduce_saved(root, case)

    def test_changed_original_video_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            (root / "reference_corner.mkv").write_bytes(b"changed diagnostic stand-in")
            with self.assertRaisesRegex(ValueError, "video hashes missing or changed"):
                module.reduce_saved(root, case)

    def test_missing_classification_review_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            case = self.make_diagnostic(root)
            review_path = root / "goods-review.json"
            review = json.loads(review_path.read_text())
            review.pop("commercial_classification_source_id")
            write(review_path, review)
            with self.assertRaisesRegex(ValueError, "classification review required"):
                module.reduce_saved(root, case)


if __name__ == "__main__":
    unittest.main()
