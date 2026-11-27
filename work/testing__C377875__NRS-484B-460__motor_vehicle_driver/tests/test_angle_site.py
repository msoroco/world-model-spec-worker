import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("angle_site", ROOT / "angle_site.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(root):
    records = {
        "map": {"source": "reviewed original map", "opendrive_sha256": "a" * 64},
        "roadway": {"district": "business", "highway_status": "reviewed_original", "curb_edge_xy": [[0, 0], [10, 0]]},
        "official_device": {"official_status": "reviewed_original", "content_review": "original device face", "indicated_angle_degrees": 45, "governed_space_polygon_xy": [[0, 0], [10, 0], [10, 10], [0, 10]], "prop_blueprint_id": "static.prop.sign", "prop_pose": {"x": 2, "y": 2, "z": 0, "yaw_deg": 0}},
        "authority": {"source": "reviewed original authority"},
        "vehicle": {"source": "reviewed original vehicle"},
        "purpose": {"activity_review": "reviewed_original"},
    }
    sources = {}
    for name, record in records.items():
        p = root / (name + ".json")
        p.write_text(json.dumps(record))
        sources[name] = {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    case = module.ASSIGNMENT + "__park_indicated"
    site = {"assignment_id": module.ASSIGNMENT, "case_id": case, "sources": sources,
            "target_xy": [5, 5], "approach_xy": [5, 20], "requested_activity": "park", "requested_orientation": "indicated", "map_id": "Town01", "road_id": 1, "vehicle_blueprint_id": "vehicle.tesla.model3", "target_heading_degrees": 45, "approach_heading_degrees": -90}
    path = root / "site.json"
    path.write_text(json.dumps(site))
    return path, case


class AngleSiteTests(unittest.TestCase):
    def test_accepts_exact_source_sealed_reviewed_geometry(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            path, case = fixture(Path(tmp))
            site, records = module.load_site(path, case)
            self.assertEqual(site["case_id"], case)
            self.assertEqual(records["official_device"]["indicated_angle_degrees"], 45)

    def test_changed_device_packet_rejected(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            path, case = fixture(Path(tmp))
            (Path(tmp) / "official_device.json").write_text('{"indicated_angle_degrees": 90}')
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                module.load_site(path, case)

    def test_unreviewed_device_and_outside_space_rejected(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            path, case = fixture(root)
            site = json.loads(path.read_text())
            site["target_xy"] = [20, 20]
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "governed space"):
                module.load_site(path, case)
            site["target_xy"] = [5, 5]
            device = root / "official_device.json"
            item = json.loads(device.read_text())
            item["official_status"] = "assumed"
            device.write_text(json.dumps(item))
            site["sources"]["official_device"]["sha256"] = hashlib.sha256(device.read_bytes()).hexdigest()
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "official angle-parking device"):
                module.load_site(path, case)

    def test_wrong_case_or_activity_rejected(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            path, case = fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, "wrong angle-parking"):
                module.load_site(path, module.ASSIGNMENT + "__stop_offset")
            site = json.loads(path.read_text())
            site["requested_activity"] = "stop"
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "exact activity"):
                module.load_site(path, case)


if __name__ == "__main__":
    unittest.main()
