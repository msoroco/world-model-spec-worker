import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_measurement import ASSIGNMENT, _overlap_area, _polygon, measure
from comparison_audit import audit


class AccessMeasurementTests(unittest.TestCase):
    def _attempt(self, root, access_kind="driveway", body_x=0.0):
        case = ASSIGNMENT + "__" + access_kind + "_overlap"
        frames = [{"frame": i, "time_s": round(i / 20, 2)} for i in range(900)]
        geometry = {"source_kind": "original_native_geometry", "highway_status": True,
                    "cul_de_sac": False, "highway_source": "map road metadata",
                    "alley_classification_source": "map classification and field review",
                    "cul_de_sac_source": "connected end geometry",
                    "property_abutting_source": "parcel boundary survey", "property_id": "parcel-1",
                    "driveway_ownership_source": "parcel access survey",
                    "vehicular_use_source": "original driveway path survey",
                    "access_corridor_polygon_m": [[0, 0], [4, 0], [4, 5], [0, 5]],
                    "access_kind": access_kind, "ego_vehicle_id": "ego"}
        polygon = [[body_x, 1], [body_x + 2, 1], [body_x + 2, 3], [body_x, 3]]
        body = {"case_id": case, "source_kind": "original_native",
                "samples": [{"frame": r["frame"], "time_s": r["time_s"],
                             "vehicle_id": "ego", "polygon_m": polygon} for r in frames]}
        activity = {"case_id": case, "source_kind": "original_native",
                    "samples": [{"frame": r["frame"], "time_s": r["time_s"],
                                 "state": "parked" if r["frame"] >= 100 else "approaching",
                                 "speed_mps": 0 if r["frame"] >= 100 else 2} for r in frames]}
        packets = {"frame_map": {"frames": frames}, "alley_geometry": geometry,
                   "vehicle_footprint": body, "activity": activity}
        sources = {}
        for name, value in packets.items():
            raw = (json.dumps(value) + "\n").encode()
            (root / (name + ".json")).write_bytes(raw)
            sources[name] = {"path": name + ".json", "sha256": hashlib.sha256(raw).hexdigest()}
        return case, {"case_id": case, "source_kind": "original_native", "sources": sources}

    def test_convex_overlap_and_clearance(self):
        access = _polygon([[0, 0], [4, 0], [4, 5], [0, 5]], "access")
        self.assertAlmostEqual(_overlap_area(_polygon([[1, 1], [3, 1], [3, 3], [1, 3]], "body"), access), 4)
        self.assertEqual(_overlap_area(_polygon([[5, 1], [7, 1], [7, 3], [5, 3]], "body"), access), 0)
        self.assertRaisesRegex(ValueError, "convex", _polygon,
                               [[0, 0], [3, 0], [1, 1], [3, 3], [0, 3]], "bad")

    def test_original_overlap_and_clear_cases(self):
        for kind in ("driveway", "entrance"):
            for x, expected in ((1.0, 4.0), (5.0, 0.0)):
                with self.subTest(kind=kind, x=x), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    case, inventory = self._attempt(root, kind, x)
                    result = measure(root, inventory, case)
                    self.assertEqual(result["original_frames"], 900)
                    self.assertEqual(result["measured_halt_frames"], 800)
                    self.assertEqual(result["max_access_intrusion_area_m2"], expected)
                    self.assertEqual(result["statutory_blocking_judgment"], "unresolved")

    def test_rejects_missing_or_stale_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root)
            (root / "alley_geometry.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                measure(root, inventory, case)
            inventory["sources"].pop("activity")
            with self.assertRaisesRegex(ValueError, "complete original"):
                measure(root, inventory, case)

    def test_rejects_nonqualifying_alley_and_missing_park(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self._attempt(root)
            path = root / "alley_geometry.json"
            data = json.loads(path.read_text())
            data["cul_de_sac"] = True
            raw = (json.dumps(data) + "\n").encode()
            path.write_bytes(raw)
            inventory["sources"]["alley_geometry"]["sha256"] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "qualifying alley"):
                measure(root, inventory, case)
            data["cul_de_sac"] = False
            data["property_abutting_source"] = ""
            raw = (json.dumps(data) + "\n").encode()
            path.write_bytes(raw)
            inventory["sources"]["alley_geometry"]["sha256"] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "abutting driveway"):
                measure(root, inventory, case)

    def test_comparison_isolates_position_and_rejects_changed_access(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            clear, overlap = base / "clear", base / "overlap"
            clear.mkdir()
            overlap.mkdir()
            for root, x, name in ((clear, 5.0, "clear"), (overlap, 1.0, "overlap")):
                _, inventory = self._attempt(root, "driveway", x)
                case = ASSIGNMENT + "__driveway_" + name
                for packet_name in ("vehicle_footprint", "activity"):
                    path = root / (packet_name + ".json")
                    packet = json.loads(path.read_text())
                    packet["case_id"] = case
                    raw = (json.dumps(packet) + "\n").encode()
                    path.write_bytes(raw)
                    inventory["sources"][packet_name]["sha256"] = hashlib.sha256(raw).hexdigest()
                inventory["case_id"] = case
                (root / "inventory.json").write_text(json.dumps(inventory))
            result = audit(clear, overlap, "driveway")
            self.assertEqual(result["measured_max_intrusion_area_m2"], [0.0, 4.0])
            path = overlap / "alley_geometry.json"
            geometry = json.loads(path.read_text())
            geometry["property_id"] = "other-parcel"
            raw = (json.dumps(geometry) + "\n").encode()
            path.write_bytes(raw)
            inventory = json.loads((overlap / "inventory.json").read_text())
            inventory["sources"]["alley_geometry"]["sha256"] = hashlib.sha256(raw).hexdigest()
            (overlap / "inventory.json").write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, "fixed alley/access conditions changed"):
                audit(clear, overlap, "driveway")


if __name__ == "__main__":
    unittest.main()
