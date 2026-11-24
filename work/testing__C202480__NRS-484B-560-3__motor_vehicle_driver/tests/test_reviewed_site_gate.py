"""Source-gated preflight tests; generated roads are diagnostic only."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from reviewed_site_gate import verify

CASE = 'testing__C202480__NRS-484B-560-3__motor_vehicle_driver__two_marked_single_right'
SOURCE = HERE / 'diagnostic_sources/two_marked_single_right/site'
PLAN = HERE / 'case-plan.json'


def road():
    def lane(index):
        return f'<lane id="{index}" type="driving"><roadMark sOffset="0" type="solid"/></lane>'
    return ('<OpenDRIVE><road id="crossing-road" length="100"><lanes>'
            '<laneSection s="0"><left>' + lane(1) + '</left><right>' +
            lane(-1) + '</right></laneSection></lanes></road></OpenDRIVE>')


class ReviewedSiteGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        for path in SOURCE.iterdir():
            if path.is_file():
                shutil.copyfile(path, self.folder / path.name)
        self.packet_path = self.folder / 'packet.json'
        self.packet = json.loads(self.packet_path.read_text())
        source = self.folder / 'opendrive.txt'
        source.write_text(road())
        self.packet['sources']['opendrive']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.packet['opendrive_road_id'] = 'crossing-road'
        self.packet['opendrive_lane_section_s_m'] = 5
        for lane, lane_id in zip(self.packet['marked_lanes'], (-1, 1)):
            lane['opendrive_lane_id'] = lane_id
        markings = self.folder / 'lane_markings.txt'
        markings.write_text(json.dumps({'marked_lanes': self.packet['marked_lanes']}) + '\n')
        self.packet['sources']['lane_markings']['sha256'] = hashlib.sha256(
            markings.read_bytes()).hexdigest()
        self.write_packet()

    def write_packet(self):
        self.packet_path.write_text(json.dumps(self.packet, indent=2) + '\n')

    def test_source_shaped_diagnostic_join(self):
        result = verify(self.packet_path, PLAN, CASE, diagnostic=True)
        self.assertEqual(result['marked_lane_ids'], [-1, 1])
        self.assertTrue(result['diagnostic'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_production_rejects_missing_independent_review(self):
        with self.assertRaisesRegex(ValueError, 'independent original site source review missing'):
            verify(self.packet_path, PLAN, CASE)

    def test_changed_road_source_rejected(self):
        path = self.folder / 'opendrive.txt'
        path.write_text(path.read_text().replace('solid', 'broken', 1))
        with self.assertRaisesRegex(ValueError, 'site source hash differs'):
            verify(self.packet_path, PLAN, CASE, diagnostic=True)

    def test_declared_lane_identity_rejected(self):
        self.packet['marked_lanes'][0]['opendrive_lane_id'] = -2
        markings = self.folder / 'lane_markings.txt'
        markings.write_text(json.dumps({'marked_lanes': self.packet['marked_lanes']}) + '\n')
        self.packet['sources']['lane_markings']['sha256'] = hashlib.sha256(
            markings.read_bytes()).hexdigest()
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'declared total marked highway lanes differ'):
            verify(self.packet_path, PLAN, CASE, diagnostic=True)


if __name__ == '__main__':
    unittest.main()
