"""Synthetic source packet tests; no municipal or Native evidence is claimed."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hydrant import ASSIGNMENT
from native_packet import REQUIRED_SOURCES, VIEWS, validate_packet
from test_hydrant import site as fixture_site


class PacketTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT.parents[1] / '.runtime-work' / 'c150098-packet-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = ASSIGNMENT + '__upstream_inside'
        site = fixture_site()
        sources = {}
        for name, field in REQUIRED_SOURCES.items():
            path = self.root / (name + '.json')
            payload = (json.dumps([dict(name=n, width=w, height=h,
                                        pose_source='survey', location_xyz_m=[1, 2, 3],
                                        rotation_rpy_deg=[0, 0, 0])
                                   for n, w, h in VIEWS]) if name == 'camera_plan'
                       else name + ' original reviewed bytes')
            path.write_text(payload, encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            sources[name] = dict(path=path.name, sha256=digest,
                                 citation='synthetic unit source', reviewer='fixture')
            site[field] = digest
        self.packet = self.root / 'reviewed-site.json'
        self.payload = dict(review_status='reviewed', reviewer='fixture',
                            case_id=self.case_id, site=site, sources=sources,
                            planned_case=dict(side='upstream', gap_m=4.422,
                                              activity='park', exception='none'))
        self.save()

    def save(self):
        self.packet.write_text(json.dumps(self.payload), encoding='utf-8')

    def test_exact_source_bound_packet(self):
        site, case, hashes, cameras = validate_packet(self.packet, self.case_id)
        self.assertEqual(case.suffix, 'upstream_inside')
        self.assertEqual(hashes['opendrive'], site['map_sha256'])
        self.assertEqual(len(cameras), 4)

    def test_changed_source_and_missing_authority_rejected(self):
        (self.root / 'opendrive.json').write_text('altered', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source bytes changed: opendrive'):
            validate_packet(self.packet, self.case_id)
        (self.root / 'opendrive.json').write_text('opendrive original reviewed bytes', encoding='utf-8')
        self.payload['sources'].pop('parallel_parking_authority')
        self.save()
        with self.assertRaisesRegex(ValueError, 'reviewed source required: parallel_parking_authority'):
            validate_packet(self.packet, self.case_id)

    def test_exact_case_and_review_required(self):
        with self.assertRaisesRegex(ValueError, 'exact case differs'):
            validate_packet(self.packet, ASSIGNMENT + '__downstream_inside')
        self.payload['review_status'] = 'draft'
        self.save()
        with self.assertRaisesRegex(ValueError, 'reviewed original site packet required'):
            validate_packet(self.packet, self.case_id)

    def test_exact_construction_and_camera_pose_required(self):
        self.payload['planned_case']['gap_m'] = 4.572
        self.save()
        with self.assertRaisesRegex(ValueError, 'exact construction differs'):
            validate_packet(self.packet, self.case_id)
        self.payload['planned_case']['gap_m'] = 4.422
        camera_path = self.root / 'camera_plan.json'
        cameras = json.loads(camera_path.read_text())
        cameras[0]['location_xyz_m'] = ['unknown', 0, 0]
        camera_path.write_text(json.dumps(cameras), encoding='utf-8')
        digest = hashlib.sha256(camera_path.read_bytes()).hexdigest()
        self.payload['sources']['camera_plan']['sha256'] = digest
        self.payload['site']['camera_plan_sha256'] = digest
        self.save()
        with self.assertRaisesRegex(ValueError, 'camera pose missing'):
            validate_packet(self.packet, self.case_id)


if __name__ == '__main__':
    unittest.main()
