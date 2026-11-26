import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from posted_site import load


CASE = "testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__above"


class PostedSiteTests(unittest.TestCase):
    def packet(self):
        packet = {"case_id": CASE, "source_kind": "reviewed_original_site",
                  "governed_road_id": "road", "governed_segment_id": "segment",
                  "governed_direction": "forward", "vehicle_id": "ego",
                  "sign_id": "sign", "sign_jurisdiction": "jurisdiction",
                  "sign_installation_record": "record", "unit": "mph", "rate": 25,
                  "public_authority_posted": True, "sign_in_camera_view": True,
                  "travel_lanes": {"forward": "lane-a", "opposite": "lane-b"}}
        for key in ("highway_dedication_source", "public_access_source",
                    "narrow_road_geometry_source", "vehicle_clearance_source",
                    "governed_segment_source", "governed_direction_source",
                    "sign_position_source", "posting_authority_source"):
            packet[key] = "original-review/" + key
        return packet

    def check(self, packet, sha_override=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "site.json"
            raw = json.dumps(packet).encode()
            path.write_bytes(raw)
            return load(path, sha_override or hashlib.sha256(raw).hexdigest(), CASE)

    def test_reviewed_packet(self):
        self.assertEqual(self.check(self.packet())["rate"], 25)

    def test_missing_authority_source(self):
        packet = self.packet()
        packet.pop("posting_authority_source")
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.check(packet)

    def test_off_camera_requires_reading_source(self):
        packet = self.packet()
        packet["sign_in_camera_view"] = False
        with self.assertRaisesRegex(ValueError, "off-camera"):
            self.check(packet)

    def test_opposing_lane_must_be_distinct(self):
        packet = self.packet()
        packet["travel_lanes"]["opposite"] = "lane-a"
        with self.assertRaisesRegex(ValueError, "distinct"):
            self.check(packet)

    def test_stale_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.check(self.packet(), "0" * 64)
