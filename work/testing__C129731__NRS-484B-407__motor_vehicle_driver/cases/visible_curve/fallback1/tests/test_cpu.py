import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageTests(unittest.TestCase):
    def test_geometry(self):
        g = load('geometry')
        proof = g.plan_check()
        self.assertTrue(proof['two_way_lanes'])
        self.assertAlmostEqual(g.FEET_500_M, 152.4)
        self.assertNotEqual(g.point(180), g.point(200))

    def test_controller_direction_change(self):
        c = load('controller')
        route = [(0., 0., 0., True), (1., 0., 0., True),
                 (2., 0., 0., False), (1., 0., 0., False)]
        self.assertEqual(c.next_index(route, 1, (1., 0.), 1.)[1], True)
        self.assertEqual(c.next_index(route, 1, (1., 0.), 0.)[0], 2)
        self.assertLessEqual(abs(c.command((0, 0), 0, 0, (1, 2))['steer']), .65)

    def test_saved_audit_rejects_missing_visibility(self):
        audit = load('delivery_audit')
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'Missing required source: trace.jsonl'):
                audit.audit(pathlib.Path(temporary), 'case')

    def test_visibility_finalizer_positive_and_negative_source(self):
        analysis = load('analysis')
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            with self.assertRaisesRegex(ValueError, 'Missing required source: visibility_history.jsonl'):
                analysis.measure_visibility(root)
            original = {'frame': 1, 'time_s': 0.05,
                'visibility': {'probe_distance_m': 152.4, 'approaches': [
                    {'lane_id': -1, 'any_sample_clear_at_probe': True,
                     'body_rays_at_probe': [{'clear': True}] * 9},
                    {'lane_id': 1, 'any_sample_clear_at_probe': False,
                     'body_rays_at_probe': [{'clear': False}] * 9}]}}
            (root / 'visibility_history.jsonl').write_text(json.dumps(original) + '\n')
            measured = analysis.measure_visibility(root)
            self.assertEqual(measured['distance_m'], 152.4)
            self.assertEqual(len(measured['samples'][0]['approaches']), 2)
            self.assertEqual(measured['legal_visibility_standard'], 'unresolved')

    def test_saved_audit_joins_both_directions(self):
        audit = load('delivery_audit')
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            for name in ['trace.jsonl', 'video_frames.jsonl', 'turn_history.jsonl',
                         'approach_history.jsonl', 'visibility_history.jsonl']:
                rows = []
                for i in range(2):
                    row = {'frame': i + 100, 'time_s': i * .05}
                    if name == 'video_frames.jsonl':
                        row = {'carla_frame': i + 100, 'video_frame': i, 'time_s': i * .05}
                    if name in ('turn_history.jsonl', 'approach_history.jsonl'):
                        row['body_vertices_m'] = [[0, 0, 0]] * 4
                    if name == 'visibility_history.jsonl':
                        row['visibility'] = {'probe_distance_m': 152.4,
                            'approaches': [{'lane_id': side,
                                'body_rays_at_probe': [{'clear': True}] * 9} for side in (-1, 1)]}
                    rows.append(row)
                (root / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))
            self.assertEqual(audit.audit(root, 'case')['frames'], 2)
            changed = [json.loads(s) for s in (root / 'visibility_history.jsonl').read_text().splitlines()]
            changed[1]['visibility']['approaches'].pop()
            (root / 'visibility_history.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in changed))
            with self.assertRaisesRegex(ValueError, 'Both incoming approaches absent'):
                audit.audit(root, 'case')


if __name__ == '__main__':
    unittest.main()
