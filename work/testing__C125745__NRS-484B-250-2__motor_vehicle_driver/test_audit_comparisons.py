import json
import tempfile
import unittest
from pathlib import Path

from audit_comparisons import audit


class OriginalComparisonTests(unittest.TestCase):
    def packet(self, case, ego_entry, other_entry=80):
        def body(index, entry):
            x = 1 if index >= entry else -3
            return [[x, 4], [x + 1, 4], [x + 1, 5], [x, 5]]
        packet = {"case_id": case, "source_kind": "original_native",
                  "map_source_sha256": "fake-map", "intersection_source_sha256": "fake-intersection",
                  "highway_source_sha256": "fake-highways", "device_source_sha256": "fake-device",
                  "ego_road_id": 3, "other_road_id": 4,
                  "ego_actor_id": 11, "other_actor_id": 12,
                  "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
                  "frames": []}
        for index in range(900):
            packet["frames"].append({"frame": index, "time_s": index / 20,
                                     "ego": {"id": 11, "road_id": 3,
                                             "body_corners_xy_m": body(index, ego_entry)},
                                     "other": {"id": 12, "road_id": 4,
                                               "body_corners_xy_m": body(index, other_entry)}})
        return packet

    def sources(self, directory):
        root = Path(directory)
        result = {}
        for suffix, entry in (("entry_below", 40), ("entry_inside", 80),
                              ("entry_above", 120)):
            case = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver__" + suffix
            path = root / (suffix + ".json")
            path.write_text(json.dumps(self.packet(case, entry)) + "\n")
            result[case] = str(path)
        return result

    def test_two_ordered_pairs_with_fixed_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit(self.sources(directory))
            self.assertEqual(len(report["comparisons"]), 2)
            self.assertTrue(all(p["fixed_source_checks_passed"] for p in report["comparisons"]))
            self.assertEqual(report["legal_applicability"], "unresolved")

    def test_rejects_changed_fixed_intersection_source(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = self.sources(directory)
            path = Path(sources[next(case for case in sources if case.endswith("entry_above"))])
            packet = json.loads(path.read_text())
            packet["intersection_source_sha256"] = "different"
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed map"):
                audit(sources)

    def test_rejects_diagnostic_as_original(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = self.sources(directory)
            path = Path(sources[next(case for case in sources if case.endswith("entry_inside"))])
            packet = json.loads(path.read_text())
            packet["diagnostic_fixture"] = True
            path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "synthetic timing source"):
                audit(sources)
