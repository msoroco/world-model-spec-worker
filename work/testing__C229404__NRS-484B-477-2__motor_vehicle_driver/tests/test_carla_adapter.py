import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_measurement import ASSIGNMENT
from carla_alley_adapter import CameraBuffer, validate_packet


class PacketTests(unittest.TestCase):
    def packet(self, root, case_id):
        source_names = ("opendrive_source", "highway_source", "alley_classification_source",
                        "cul_de_sac_source", "start_connection_source", "end_connection_source",
                        "property_abutting_source", "driveway_ownership_source",
                        "vehicular_use_source")
        packet = {"case_id": case_id, "reviewer": "local original-source reviewer",
                  "source_kind": "original_native_geometry", "highway_status": True,
                  "cul_de_sac": False, "property_id": "parcel-1", "access_kind": "driveway",
                  "vehicle_blueprint_id": "vehicle.test", "ego_vehicle_id": "ego",
                  "spawn_xyz_m": [0, 0, 0], "spawn_rpy_deg": [0, 0, 0],
                  "centerline_start_m": [-50, 2], "centerline_end_m": [100, 2],
                  "ego_length_m": 4.5, "ego_width_m": 1.8,
                  "access_corridor_polygon_m": [[0, 0], [4, 0], [4, 5], [0, 5]],
                  "cameras": []}
        for name in source_names:
            path = root / (name + ".txt")
            path.write_text("reviewed original source for " + name + "\n")
            packet[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                     ("reference_corner", 1280, 720),
                                     ("driver_reference", 1280, 720)):
            packet["cameras"].append({"name": name, "width": width, "height": height,
                                       "fov_deg": 75, "location_xyz_m": [1, 2, 3],
                                       "rotation_rpy_deg": [0, 0, 0],
                                       "pose_source": "reviewed survey", "reviewer": "local reviewer"})
        path = root / "packet.json"
        path.write_text(json.dumps(packet) + "\n")
        return path, packet

    def test_source_hash_and_four_camera_plan(self):
        case = ASSIGNMENT + "__driveway_clear"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, packet = self.packet(root, case)
            self.assertEqual(validate_packet(path, case)["case_id"], case)
            with self.assertRaisesRegex(ValueError, "packet case or reviewer"):
                validate_packet(path, ASSIGNMENT + "__driveway_overlap")
            Path(packet["highway_source"]["path"]).write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "source changed"):
                validate_packet(path, case)

    def test_missing_camera_provenance_rejected(self):
        case = ASSIGNMENT + "__driveway_overlap"
        with tempfile.TemporaryDirectory() as directory:
            path, packet = self.packet(Path(directory), case)
            packet["cameras"][2].pop("pose_source")
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "pose provenance"):
                validate_packet(path, case)

    def test_camera_buffer_joins_native_frame(self):
        buffer = CameraBuffer()
        rgb = Image.new("RGBA", (2, 2), (12, 23, 34, 255))
        raw = rgb.tobytes("raw", "BGRA")
        frame = type("Frame", (), {"frame": 19, "width": 2, "height": 2,
                                   "raw_data": raw})()
        buffer.receive("overview", 2, 2, frame)
        with Image.open(io.BytesIO(buffer.read("overview", 19))) as result:
            self.assertEqual(result.convert("RGB").getpixel((0, 0)), (12, 23, 34))
        buffer.receive("overview", 3, 2, frame)
        with self.assertRaisesRegex(ValueError, "callback failed"):
            buffer.read("overview", 19)


if __name__ == "__main__":
    unittest.main()
