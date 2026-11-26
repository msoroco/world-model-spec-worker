"""Case-specific saved measurement and joined source tests."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis import check_joins, diagnostic, measure_hydrant_distance
from hydrant import ASSIGNMENT, CASES
from test_native_packet import PacketTest


class AnalysisTest(unittest.TestCase):
    setUp = PacketTest.setUp
    save = PacketTest.save

    def test_diagnostic_sources_and_full_join(self):
        site = self.payload['site']
        site_path = self.root / 'site.json'
        site_path.write_text(json.dumps(site), encoding='utf-8')
        site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
        case = CASES[0]
        fixed = {'actor_id': 11, 'hydrant_actor_id': 22,
                 'map_sha256': site['map_sha256'], 'site_sha256': site_sha,
                 'hydrant_identity_sha256': site['hydrant_identity_sha256'],
                 'hydrant_geometry_sha256': site['hydrant_geometry_sha256'],
                 'parallel_parking_authority_sha256': site['parallel_parking_authority_sha256'],
                 'camera_plan_sha256': site['camera_plan_sha256']}
        history = [dict(fixed, case_id=self.case_id, frame=100 + i,
                        time_s=i / 20, hydrant_physically_present=True,
                        body_source_sha256='body-fixture', frame_map_sha256='map-fixture',
                        body_west_x_m=-8.422, body_east_x_m=-4.422,
                        activity_observation='parked', exception_kind='none')
                   for i in range(900)]
        history_path = self.root / 'original-hydrant-history.jsonl'
        history_path.write_text(''.join(json.dumps(row) + '\n' for row in history), encoding='utf-8')
        (self.root / 'diagnostic-source-note.json').write_text(json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False, 'case_id': self.case_id}), encoding='utf-8')
        cameras = [dict(frame_index=i, native_frame=100 + i,
                        time_s=i / 20, camera_frames={name: 100 + i for name in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')})
                   for i in range(900)]
        videos = [dict(video_frame=i, carla_frame=100 + i, native_frame=100 + i,
                       time_s=i / 20) for i in range(900)]
        (self.root / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in cameras), encoding='utf-8')
        (self.root / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in videos), encoding='utf-8')
        checked_site, source = diagnostic(self.root, self.case_id)
        self.assertEqual(checked_site, site)
        self.assertEqual(set(source), {'site.json', 'original-hydrant-history.jsonl',
                                      'diagnostic-source-note.json'})
        check_joins(self.root, history)
        measured = measure_hydrant_distance(site, history, case)
        self.assertAlmostEqual(measured['minimum_longitudinal_gap_m'], 4.422)
        cameras[5]['camera_frames']['overview'] = 999
        (self.root / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in cameras), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'frame join changed'):
            check_joins(self.root, history)
        history_path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: original-hydrant-history.jsonl'):
            diagnostic(self.root, self.case_id)


if __name__ == '__main__':
    unittest.main()
