import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("four_camera", ROOT / "four_camera.py")
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class CameraTests(unittest.TestCase):
    def test_four_raw_packet_shapes(self):
        encoder = camera.FourCameraEncoder(ROOT)
        packets = {name:NS(width=size[0], height=size[1], raw_data=bytes(size[0]*size[1]*4))
                   for name,size in camera.CAMERA_SIZES.items()}
        encoder.validate_packets(packets)
        packets["approach"].width -= 1
        with self.assertRaisesRegex(ValueError, "Camera pixels"):
            encoder.validate_packets(packets)


if __name__ == "__main__":
    unittest.main()
