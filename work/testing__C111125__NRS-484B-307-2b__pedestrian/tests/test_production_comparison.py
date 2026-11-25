import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

import production_comparison_audit as production


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProductionComparisonTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111125-production-pair-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def attempt(self, suffix, mode):
        root = self.root / suffix
        root.mkdir()
        content = {
            'map.json': {'public_highway': True,
                         'highway_polygon_xy': [[0, 0], [10, 0], [10, 10], [0, 10]],
                         'crosswalk_polygon_xy': [[0, 4], [10, 4], [10, 6], [0, 6]],
                         'crosswalk_kind': 'marked', 'crosswalk_qualifies': True},
            'head.json': {'official': True, 'control': 'traffic_light',
                          'head_id': 'head1', 'pedestrian_faces_head': True},
            'devices.json': {'other_device_id': 'ped1', 'inventory_complete': True},
        }
        refs = []
        for name, value in content.items():
            path = root / name
            path.write_text(json.dumps(value) + '\n')
            refs.append({'path': name, 'sha256': sha(path)})
        site = {'cell_id': 'C111125', 'actor': 'pedestrian',
                'original_sources': refs, 'map_source_path': 'map.json',
                'signal_source_path': 'head.json',
                'device_inventory_source_path': 'devices.json',
                'official_signal_head_id': 'head1', 'pedestrian_faces_head': True,
                'public_highway_source_assertion': True,
                'crosswalk_qualification_source_assertion': True,
                'crosswalk_kind': 'marked',
                'highway_polygon_xy': content['map.json']['highway_polygon_xy'],
                'crosswalk_polygon_xy': content['map.json']['crosswalk_polygon_xy'],
                'pedestrian_route_xy': [[-2, 5], [2, 5], [11, 5]],
                'other_device_id': 'ped1'}
        (root / 'site-source.json').write_text(json.dumps(site) + '\n')
        rows = []
        for frame in range(900):
            x = -2 if frame < 100 else (2 if frame <= 300 else 11)
            rows.append({'frame': frame, 'elapsed_seconds': frame / 20,
                         'official_signal_head_id': 'head1',
                         'pedestrian_faces_head': True,
                         'lit_aspects': ['circular_green'],
                         'pedestrian_xy': [x, 5], 'other_device_id': 'ped1',
                         'other_device_indication': 'none' if mode == 'absent' else 'WALK',
                         'other_device_mode': mode,
                         'other_device_countdown': None})
        frames = root / 'original-frames.json'
        frames.write_text(json.dumps(rows) + '\n')
        (root / 'capture-receipt.json').write_text(json.dumps({
            'case_id': ROOT.name + '__' + suffix,
            'original_frames': {'path': frames.name, 'sha256': sha(frames)},
        }) + '\n')
        (root / 'config.json').write_text(json.dumps({'cameras': [
            {'name': name, 'width': 1920 if name == 'overview' else 1280,
             'height': 1080 if name == 'overview' else 720}
            for name in ('overview', 'approach', 'reference_corner',
                         'driver_reference')]}) + '\n')
        return root

    def test_original_saved_source_pair_and_changed_fixed_head(self):
        left = self.attempt('marked_cross', 'absent')
        right = self.attempt('walk_cross', 'walk')
        with patch.object(production, 'verify', return_value={'physical_acceptance': False}):
            result = production.run('device_alternative_walk_cross', left, right)
            self.assertEqual(result['observations']['device_mode_checked'], 'walk')
            self.assertFalse(result['physical_acceptance'])
            head = right / 'head.json'
            value = json.loads(head.read_text())
            value['review_note'] = 'different original signal source'
            head.write_text(json.dumps(value) + '\n')
            site_path = right / 'site-source.json'
            site = json.loads(site_path.read_text())
            next(ref for ref in site['original_sources'] if ref['path'] == 'head.json')['sha256'] = sha(head)
            site_path.write_text(json.dumps(site) + '\n')
            with self.assertRaisesRegex(ValueError, 'fixed condition differs'):
                production.run('device_alternative_walk_cross', left, right)


if __name__ == '__main__':
    unittest.main()
