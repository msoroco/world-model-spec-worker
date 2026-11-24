import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime/scenario_pipeline"))
from native_output_bridge import publish


class BridgeTests(unittest.TestCase):
    def test_fake_native_publication_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ["TMPDIR"])) as temporary:
            root = Path(temporary)
            (root / "runner.py").write_text("# original materialized runner\n")
            (root / "construction.json").write_text('{}\n')
            map_bytes = b"<OpenDRIVE>original test source</OpenDRIVE>"
            map_sha = hashlib.sha256(map_bytes).hexdigest()
            image = io.BytesIO()
            Image.new("RGB", (4, 4), "blue").save(image, format="PNG")
            png = image.getvalue()
            png_sha = hashlib.sha256(png).hexdigest()
            rows = []
            for index in range(900):
                frame = index + 100
                cameras = {}
                for view in ("front", "rear", "left", "right"):
                    path = root / "cameras" / view / f"{frame:06d}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(png)
                    cameras[view] = png_sha
                rows.append({"frame_id": frame, "sim_time_s": index / 20,
                             "parked_position_m": [1.0, 2.0, 0.0],
                             "parked_heading_deg": 0.0,
                             "parked_velocity_mps": [0.0, 0.0, 0.0],
                             "parked_speed_mps": 0.0,
                             "parked_body_vertices_m": [[0, 0, 0], [2, 0, 0],
                                                        [2, 3, 0], [0, 3, 0]],
                             "parked_blueprint": "vehicle.test.car",
                             "passing_blueprint": "vehicle.test.car",
                             "parked_blueprint_attributes": {"base_type": "car"},
                             "passing_blueprint_attributes": {"base_type": "car"},
                             "passing_position_m": [3.0, 1.0, 0.0],
                             "passing_heading_deg": 0.0,
                             "passing_velocity_mps": [2.0, 0.0, 0.0],
                             "passing_body_vertices_m": [[2, 0, 0], [4, 0, 0],
                                                          [4, 3, 0], [2, 3, 0]],
                             "driver_blueprint": "walker.pedestrian.test",
                             "driver_blueprint_attributes": {"age": "adult"},
                             "driver_heading_deg": 0.0,
                             "driver_velocity_mps": [0.0, 0.0, 0.0],
                             "driver_speed_mps": 0.0,
                             "driver_body_vertices_m": [[0, 0, 0], [1, 0, 0],
                                                        [1, 1, 0], [0, 1, 0]],
                             "observed_act": "open" if index == 1 else "none",
                             "act_side": "left" if index == 1 else None,
                             "passing_body_xy": [[3, 0], [3, 3]],
                             "passing_speed_mps": 2.0,
                             "camera_sha256": cameras})
            trace = {"source_kind": "native_original", "frames": rows,
                     "fixed_context": {"map_sha256": map_sha,
                                       "survey_sha256": "survey-test",
                                       "parked_vehicle_id": "1",
                                       "passing_vehicle_id": "2",
                                       "driver_id": "3"}}
            (root / "native-trace.json").write_text(json.dumps(trace) + "\n")
            with self.assertRaisesRegex(ValueError, "restoration"):
                publish(root, map_bytes=map_bytes, restoration_verified=False,
                        expected_frames=900)
            with self.assertRaisesRegex(ValueError, "map bytes"):
                publish(root, map_bytes=b"wrong map", restoration_verified=True,
                        expected_frames=900)
            sealed = publish(root, map_bytes=map_bytes, restoration_verified=True,
                             expected_frames=900)
            self.assertTrue(sealed.is_file())
            self.assertEqual(len((root / "capture/native/frames.jsonl").read_text().splitlines()), 900)
            self.assertEqual(len((root / "capture/evidence.jsonl").read_text().splitlines()), 900)
            self.assertEqual(len((root / "video_frames.jsonl").read_text().splitlines()), 900)
            self.assertTrue((root / "capture/native/graphs/base/00000100.adapter.json").is_file())
            first = json.loads((root / "capture/evidence.jsonl").read_text().splitlines()[0])
            self.assertEqual([actor["actor_id"] for actor in
                              first["original_observations"]["participants"]], [1, 2, 3])
            self.assertEqual(first["original_observations"]["participants"][1]["blueprint"],
                             "vehicle.test.car")
            for target in ("overview", "approach", "reference_corner", "driver_reference"):
                self.assertTrue((root / (target + ".mkv")).is_file())
            from worker_exchange.saved_processing import record_native_exit
            receipt = record_native_exit(root)
            self.assertEqual(receipt["capture_seal_sha256"], hashlib.sha256(sealed.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "already been published"):
                publish(root, map_bytes=map_bytes, restoration_verified=True,
                        expected_frames=900)


if __name__ == "__main__":
    unittest.main()
