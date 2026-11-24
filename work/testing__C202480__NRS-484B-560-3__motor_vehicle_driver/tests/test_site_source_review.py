"""Exact marked-lane OpenDRIVE checks and source drift negatives."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from site_source_review import inspect


def xml_for(count):
    left = count // 2
    right = count - left
    def lane(number):
        return f'<lane id="{number}" type="driving"><roadMark sOffset="0" type="solid"/></lane>'
    return ('<OpenDRIVE><road id="crossing-road" length="100">'
            '<lanes><laneSection s="0"><left>' +
            ''.join(lane(i) for i in range(1, left + 1)) +
            '</left><right>' +
            ''.join(lane(-i) for i in range(1, right + 1)) +
            '</right></laneSection></lanes></road></OpenDRIVE>')


class SiteSourceReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.packet = self.folder / "packet.json"
        self.source = self.folder / "road.xodr"

    def make(self, actual, declared=None):
        self.source.write_text(xml_for(actual))
        declared = actual if declared is None else declared
        left, right = declared // 2, declared - declared // 2
        identifiers = [*range(1, left + 1), *(-i for i in range(1, right + 1))]
        value = {"case_id": f"exact-{declared}", "opendrive_road_id": "crossing-road",
                 "opendrive_lane_section_s_m": 5,
                 "sources": {"opendrive": {"path": "road.xodr",
                   "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}},
                 "marked_lanes": [{"opendrive_lane_id": i} for i in identifiers]}
        self.packet.write_text(json.dumps(value))
        return value

    def test_two_four_five_marked_lane_counts_are_source_backed(self):
        for count in (2, 4, 5):
            self.make(count)
            result = inspect(self.packet)
            self.assertEqual(result["marked_highway_lane_count"], count)
            self.assertFalse(result["crossing_authority_verified"])
            self.assertFalse(result["lane_directions_verified"])

    def test_placeholder_road_cannot_support_lane_claim(self):
        self.make(4)
        self.source.write_text("<OpenDRIVE><road id='fixture'/></OpenDRIVE>")
        value = json.loads(self.packet.read_text())
        value["sources"]["opendrive"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.packet.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "selected highway road absent"):
            inspect(self.packet)

    def test_declared_count_must_match_all_driving_lanes(self):
        self.make(5, declared=4)
        with self.assertRaisesRegex(ValueError, "declared total marked highway lanes differ"):
            inspect(self.packet)

    def test_changed_opendrive_bytes_rejected(self):
        self.make(4)
        self.source.write_text(self.source.read_text().replace('type="solid"', 'type="broken"', 1))
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            inspect(self.packet)

    def test_missing_road_mark_rejected(self):
        self.make(4)
        self.source.write_text(self.source.read_text().replace('<roadMark sOffset="0" type="solid"/>', '', 1))
        value = json.loads(self.packet.read_text())
        value["sources"]["opendrive"]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.packet.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "lacks explicit road marking"):
            inspect(self.packet)


if __name__ == "__main__":
    unittest.main()
