import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
from driveway_comparisons import DIFFERENCE, audit
from driveway_measurements import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        scratch = FOLDER.parents[1] / '.runtime-work/c229404-comparison-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = json.loads((FOLDER / 'case-plan.json').read_text())
        self.cases = {item['case_id']: item for item in self.plan['cases']}
        self.map_path = self.root / 'road.xodr'
        self.map_path.write_text('<OpenDRIVE><header/></OpenDRIVE>\n')

    def ref(self, path):
        return {'path': str(path), 'sha256': sha(path)}

    def packet(self, case_id):
        case = self.cases[case_id]
        suffix = case_id.rsplit('__', 1)[1]
        folder = self.root / suffix
        folder.mkdir(exist_ok=True)
        position = case['position_target']
        distance = {'front': 0, 'within_5ft': 1, 'outside_5ft': 2}[position]
        vertices = [[x, y, z] for x in (1, 2)
                    for y in (distance, distance + 1) for z in (0, 1)]
        context = {'case_id': case_id, 'driveway_kind': case['driveway_kind'],
                   'map_sha256': sha(self.map_path),
                   'mouth_start_xy': [0, 0], 'mouth_end_xy': [3, 0]}
        for key in ('mouth_source', 'frontage_source', 'driveway_use_source',
                    'responsible_person_source', 'relationship_source',
                    'purpose_source', 'traffic_direction_source', 'postal_status_source'):
            context[key] = 'fixture-shaped-source:' + key
        context_path = folder / 'context.json'
        context_path.write_text(json.dumps(context) + '\n')
        trace_path = folder / 'trace.jsonl'
        trace_path.write_text(''.join(json.dumps({'frame': i, 'time_s': i / 20,
                                                'vehicle_vertices': vertices,
                                                'speed_mps': 0,
                                                'control_state': case['activity']}) + '\n'
                                      for i in range(20)))
        receipt_path = folder / 'receipt.json'
        receipt_path.write_text(json.dumps({'assignment_id': FOLDER.name,
                                            'case_id': case_id,
                                            'source_kind': 'original_native_capture',
                                            'diagnostic_fixture': False,
                                            'context_sha256': sha(context_path),
                                            'trace_sha256': sha(trace_path),
                                            'map_sha256': sha(self.map_path),
                                            'fps': 20, 'frame_count': 20}) + '\n')
        measured = measure(case_id, context_path, trace_path,
                           receipt_path, self.map_path)
        conditions = {name: case[name] for name in
                      ('driveway_kind', 'activity', 'position_target',
                       'driver_relationship', 'necessity_or_postal_context')}
        sources = {}
        for name, value in conditions.items():
            source = self.root / ('condition-' + name + '-' + value + '.json')
            source.write_text(json.dumps({'name': name, 'value': value,
                                          'source_kind': 'original_reviewed_record'}) + '\n')
            sources[name] = self.ref(source)
        packet = {'case_id': case_id, 'source_kind': 'original_native_capture',
                  'diagnostic_fixture': False, 'measurement': measured,
                  'source_files': {'context': self.ref(context_path),
                                   'trace': self.ref(trace_path),
                                   'receipt': self.ref(receipt_path),
                                   'map': self.ref(self.map_path)},
                  'observed_conditions': conditions, 'condition_sources': sources,
                  'observed_full_footprint_distance_m': measured['minimum_observed_full_footprint_to_mouth_m'],
                  'map_sha256': sha(self.map_path), 'capture_rate_hz': 20,
                  'responsible_person_id': 'person-1', 'jurisdiction_id': 'las-vegas'}
        for name in ('driveway_mouth', 'driveway_frontage', 'vehicle_body_spec',
                     'camera_profile'):
            source = self.root / (name + '.json')
            source.write_text(json.dumps({'name': name, 'fixture_only': True}) + '\n')
            packet[name + '_sha256'] = sha(source)
            packet['condition_sources'][name + '_sha256'] = self.ref(source)
        packet['condition_sources']['map_sha256'] = self.ref(self.map_path)
        return packet

    def pair(self, question):
        comparison = next(c for c in self.plan['comparisons']
                          if c['isolated_question'] == question)
        return [self.packet(case_id) for case_id in comparison['case_ids']]

    def test_all_eleven_exact_pairs_pass_source_shaped_audit(self):
        self.assertEqual(len(DIFFERENCE), 11)
        for question in DIFFERENCE:
            with self.subTest(question=question):
                result = audit(question, *self.pair(question), self.plan)
                self.assertEqual(result['case_ids'], next(c['case_ids'] for c in self.plan['comparisons']
                                                         if c['isolated_question'] == question))
                self.assertIsNone(result['legal_judgment'])

    def test_wrong_pair_and_undeclared_change_fail(self):
        left, right = self.pair('owner exception')
        with self.assertRaisesRegex(ValueError, 'exact pair'):
            audit('owner exception', right, left, self.plan)
        right['observed_conditions']['activity'] = 'stop'
        with self.assertRaises(ValueError):
            audit('owner exception', left, right, self.plan)

    def test_tampered_original_source_and_diagnostic_fail(self):
        left, right = self.pair('five-foot spatial boundary')
        right['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'original source packet'):
            audit('five-foot spatial boundary', left, right, self.plan)
        right['diagnostic_fixture'] = False
        trace = Path(right['source_files']['trace']['path'])
        trace.write_text(trace.read_text() + '{}\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            audit('five-foot spatial boundary', left, right, self.plan)

    def test_wrong_distance_and_condition_source_fail(self):
        left, right = self.pair('five-foot spatial boundary')
        right['observed_full_footprint_distance_m'] = 1
        with self.assertRaisesRegex(ValueError, 'distance binding'):
            audit('five-foot spatial boundary', left, right, self.plan)
        left, right = self.pair('owner exception')
        path = Path(right['condition_sources']['driver_relationship']['path'])
        path.write_text(path.read_text() + 'changed\n')
        with self.assertRaisesRegex(ValueError, 'source bytes changed'):
            audit('owner exception', left, right, self.plan)


if __name__ == '__main__':
    unittest.main()
