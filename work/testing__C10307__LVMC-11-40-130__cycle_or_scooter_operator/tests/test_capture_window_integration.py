"""Exercise the full original 900-tick window across motion and saved audit."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_controller import run_bicycle_route
from native_acquisition import seal_original_acquisition
from saved_delivery import CAMERAS, audit_saved
from test_native_acquisition import CASE
from test_native_controller import Bicycle, CARLA, World


class CaptureWindowIntegrationTests(unittest.TestCase):
    def test_900_original_ticks_reach_saved_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bike = Bicycle()
            route = run_bicycle_route(World(bike), CARLA, bike,
                                      target_speed_mps=3.0, max_frames=900,
                                      minimum_frames=900)
            context = {
                "case_id": CASE, "source_kind": "original_local_native_capture",
                "jurisdiction": {"city_of_las_vegas": True, "source": "test source map"},
                "bicycle_classification": {"human_powered": True, "moped": False,
                                           "source": "test source blueprint"},
                "alley_route": {"source": "test map geometry"},
                "rack_geometry": {"source": "test actor vertices"},
                "samples": [{"frame": row["frame_id"], "time_s": row["time_s"],
                             "weather": "clear", "surface": "dry",
                             "visibility": "clear", "pedestrians": "none near rack",
                             "curvature": "straight"} for row in route],
            }
            packet = base / "test-original-context.json"
            packet.write_text(json.dumps(context))
            acquisition = base / "acquisition"
            inventory = seal_original_acquisition(
                acquisition, CASE, route, context,
                context_source={"path": str(packet),
                                "sha256": hashlib.sha256(packet.read_bytes()).hexdigest()},
            )
            cameras = {}
            for camera in CAMERAS:
                path = acquisition / (camera + ".mkv")
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                                "color=c=black:s=64x48:r=20", "-frames:v", "900",
                                "-c:v", "ffv1", str(path)],
                               check=True, capture_output=True)
                cameras[camera] = {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "frame_ids": [row["frame_id"] for row in route],
                }
            (acquisition / "camera-manifest.json").write_text(json.dumps({
                "case_id": CASE, "source_kind": "original_live_native",
                "diagnostic_fixture": False,
                "frame_map_sha256": inventory["sources"]["frame_map"]["sha256"],
                "cameras": cameras,
            }))
            receipt = audit_saved(acquisition, CASE,
                                  expected_dimensions={name: (64, 48) for name in CAMERAS})
            self.assertEqual(receipt["frame_count"], 900)
            self.assertTrue(route[-1]["route_completed"])
            self.assertEqual(route[-1]["velocity_mps"], [0.0, 0.0, 0.0])
            self.assertEqual(receipt["legal_prudence"], "unresolved")


if __name__ == "__main__":
    unittest.main()
