import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dual_green import EvidenceError
from native_cameras import CAMERAS, DIMENSIONS, CameraCapture


class NativeCameraContractTests(unittest.TestCase):
    def test_exact_four_view_capability(self):
        self.assertEqual(CAMERAS, ("overview", "approach", "reference_corner",
                                   "driver_reference"))
        self.assertEqual(DIMENSIONS["overview"], (1920, 1080))
        self.assertTrue(all(DIMENSIONS[name] == (1280, 720) for name in CAMERAS[1:]))

    def test_unsurveyed_camera_pose_rejected_before_spawning(self):
        with self.assertRaisesRegex(EvidenceError, "source-surveyed four-camera poses missing"):
            CameraCapture(object(), object(), {}, ROOT, object())


if __name__ == "__main__":
    unittest.main()
