import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load('c179789_delivery_audit', ROOT / 'delivery_audit.py')
finalizer = load('c179789_saved_finalizer_for_audit', ROOT / 'finalizer.py')
fixture = load('c179789_saved_fixture_for_audit', ROOT / 'tests/test_finalizer.py')


class DeliveryAuditTests(unittest.TestCase):
    def test_saved_sources_and_negative_branches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture.write_fixture(root)
            config = json.loads((root / 'config.json').read_text())
            config['selected_case_id'] = audit.ASSIGNMENT + '__dry_open_traffic'
            config['condition_target'] = {'surface': 'dry', 'lane_width_m': [3, 4],
                                          'longitudinal_body_gap_m': [10, 35],
                                          'sight_distance_m': [10, 120],
                                          'precipitation_percent': [0, 5]}
            (root / 'config.json').write_text(json.dumps(config) + '\n')
            finalizer.finalize(root, root / 'analysis.json')
            receipt = audit.audit_delivery(root, root / 'analysis.json')
            self.assertEqual(receipt['frame_count'], 3)
            self.assertFalse(receipt['physical_acceptance_claimed'])
            channel = root / 'speed-channel.jsonl'
            original = channel.read_text()
            channel.write_text(original.replace('8.0', '9.0', 1))
            with self.assertRaisesRegex(ValueError, 'Derived speed differs'):
                audit.audit_delivery(root, root / 'analysis.json')
            channel.write_text(original)
            surface = root / 'surface.txt'
            surface.write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'Saved original source changed'):
                audit.audit_delivery(root, root / 'analysis.json')
            surface.write_text('Observed dry pavement in source review.\n')
            result = json.loads((root / 'result.json').read_text())
            result['measured_values']['reasonable_or_proper_judgment'] = 'proper'
            (root / 'result.json').write_text(json.dumps(result) + '\n')
            with self.assertRaisesRegex(ValueError, 'Unsupported reasonable-or-proper'):
                audit.audit_delivery(root, root / 'analysis.json')

    def test_comparison_fixed_and_changed_conditions(self):
        with tempfile.TemporaryDirectory() as folder:
            roots = {}
            baseline = {name: json.loads((ROOT / name).read_text())
                        for name in ('config.json', 'road_packet.json', 'surface_packet.json')}
            baseline['config.json']['condition_target']['lane_width_m'] = [3, 4]
            baseline['surface_packet.json']['surface'] = 'dry'
            baseline['surface_packet.json']['road_id'] = 7
            baseline['road_packet.json']['weather_profile']['precipitation'] = 0
            baseline['road_packet.json']['road_id'] = 7
            baseline['road_packet.json']['ego_spawn']['y'] = 0
            baseline['road_packet.json']['lead_spawn']['x'] = 25
            baseline['road_packet.json']['lead_spawn']['y'] = 0
            baseline['road_packet.json']['lead_target_speed_mps'] = 7
            for suffix in ('dry_open_traffic', 'wet_same_traffic', 'dense_traffic',
                           'narrow_same_traffic'):
                root = Path(folder) / suffix
                root.mkdir()
                docs = json.loads(json.dumps(baseline))
                docs['config.json']['selected_case_id'] = audit.ASSIGNMENT + '__' + suffix
                docs['road_packet.json']['case_id'] = docs['config.json']['selected_case_id']
                if suffix == 'wet_same_traffic':
                    docs['surface_packet.json']['surface'] = 'wet'
                    docs['road_packet.json']['weather_profile']['precipitation'] = 80
                elif suffix == 'dense_traffic':
                    docs['road_packet.json']['lead_spawn']['x'] += 10
                    docs['road_packet.json']['lead_target_speed_mps'] += 2
                elif suffix == 'narrow_same_traffic':
                    docs['config.json']['condition_target']['lane_width_m'] = [2.5, 2.9]
                    docs['road_packet.json']['road_id'] = 8
                    docs['surface_packet.json']['road_id'] = 8
                    docs['road_packet.json']['ego_spawn']['y'] = 50
                    docs['road_packet.json']['lead_spawn']['y'] = 50
                for name, doc in docs.items():
                    (root / name).write_text(json.dumps(doc) + '\n')
                roots[suffix] = root
            self.assertTrue(audit.audit_comparison(roots)['passed'])
            road = roots['wet_same_traffic'] / 'road_packet.json'
            doc = json.loads(road.read_text())
            doc['ego_spawn']['x'] += 1
            road.write_text(json.dumps(doc) + '\n')
            with self.assertRaisesRegex(ValueError, 'Undeclared fixed road'):
                audit.audit_comparison(roots)


if __name__ == '__main__':
    unittest.main()
