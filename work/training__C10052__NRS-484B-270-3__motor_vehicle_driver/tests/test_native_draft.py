"""Adversarial CPU checks for authored C10052 geometry and saved measurement."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE/'native'))
from engineering import NAMES, TRIGGERS, parameters
from geometry import body, check, route
from measure_facility import overlap_area, measure


class DraftTests(unittest.TestCase):
    def test_geometry_and_prefix(self):
        self.assertEqual(check()['roads'], [1, 2])
        self.assertEqual(route('probe_a')[:151], route('probe_b')[:151])
        self.assertNotEqual(route('probe_a')[-1], route('probe_b')[-1])

    def test_distinct_measured_candidates(self):
        baseline = parameters('probe_b', 'primary')
        for candidate in NAMES[1:]:
            changed = {key for key in baseline if baseline[key] != parameters('probe_b', candidate)[key]}
            self.assertEqual(len(changed), 1)
            self.assertIn('source', TRIGGERS[candidate])
            self.assertIn('metric', TRIGGERS[candidate])
            self.assertIn('failure_condition', TRIGGERS[candidate])
        self.assertEqual(len({frozenset(key for key in baseline if baseline[key] !=
                                        parameters('probe_b', candidate)[key])
                              for candidate in NAMES[1:]}), 3)

    def test_rotated_polygon_overlap(self):
        theta = math.radians(20)
        shape = body(-12, -4, (math.cos(theta), math.sin(theta)))
        area = overlap_area(shape, (-60, -5, 60, -3))
        self.assertGreater(area, 0)
        self.assertLess(area, 9.36)
        self.assertAlmostEqual(overlap_area(body(-12, -1.5), (-60, -5, 60, -3)), 0)

    def test_source_bound_pair(self):
        for suffix, expected in (('probe_a', 0), ('probe_b', 9.36)):
            folder = HERE/'draft-facility'/suffix
            receipt = measure(folder/'native_samples.jsonl',
                              folder/'road_geometry.json', folder/'exception_context.json')
            self.assertEqual(receipt['max_stopped_overlap_m2'], expected)
            self.assertEqual(receipt['observed_exception_status'], 'unresolved')
            self.assertFalse(receipt['legal_verdict_claimed'])

    def test_missing_sources_rejected(self):
        folder = HERE/'draft-facility/probe_b'
        with self.assertRaisesRegex(ValueError, 'Missing required source: absent.jsonl'):
            measure(folder/'absent.jsonl', folder/'road_geometry.json',
                    folder/'exception_context.json')
        with self.assertRaisesRegex(ValueError, 'Missing required source: absent.json'):
            measure(folder/'native_samples.jsonl', folder/'road_geometry.json',
                    folder/'absent.json')

    def test_incomplete_exception_fields_rejected(self):
        folder = HERE/'draft-facility/probe_b'
        data = json.loads((folder/'exception_context.json').read_text())
        del data['exceptions']['emergency']
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'exception_context.json'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Incomplete statutory exception fields'):
                measure(folder/'native_samples.jsonl', folder/'road_geometry.json', path)

    def test_false_road_identity_rejected(self):
        folder = HERE/'draft-facility/probe_b'
        rows = [json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines()]
        rows[0]['native_road_id'] = 99
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'native_samples.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Wrong original road identity'):
                measure(path, folder/'road_geometry.json', folder/'exception_context.json')


if __name__ == '__main__':
    unittest.main()
