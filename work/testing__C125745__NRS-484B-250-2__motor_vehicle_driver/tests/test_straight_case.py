"""CPU checks for the separate opposite-direction straight construction."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def load(name):
    path = HERE / ('straight-' + name + '.py')
    spec = importlib.util.spec_from_file_location('straight_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StraightCaseTests(unittest.TestCase):
    def test_exact_route_and_intention(self):
        control = load('median_route_control')
        straight = json.loads((HERE / 'straight-site.json').read_text())
        self.assertIs(control.validate_scene(straight), straight)
        self.assertIs(straight['other_left_turn_intended'], False)
        self.assertEqual(straight['approaches']['other']['route_xy_m'][-1], [-15, 0])
        del straight['other_left_turn_intended']
        with self.assertRaisesRegex(ValueError, 'sourced straight intention'):
            control.validate_scene(straight)
        straight['other_left_turn_intended'] = False
        straight['approaches']['other']['route_xy_m'][-1] = [15, -15]
        with self.assertRaisesRegex(ValueError, 'Commanded straight exit'):
            control.validate_scene(straight)

    def test_source_intention_guard(self):
        source = (HERE / 'straight-capture_sources.py').read_text()
        self.assertIn('other_left_turn_intended is not scene.get', source)
        analyzer = (HERE / 'straight-simultaneous_entries.py').read_text()
        self.assertIn('other_left_turn_intended") is not False', analyzer)
        finalizer = (HERE / 'straight-finalizer.py').read_text()
        self.assertIn("other_left_turn_intended') is not False", finalizer)

    def test_original_history_rejects_left_intention(self):
        analyzer = load('simultaneous_entries')
        data = json.loads((HERE / 'straight-diagnostic.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in analyzer.REQUIRED:
                (root / name).write_text(data['files'][name])
            report = analyzer.analyze(root)
            self.assertEqual(report['approach_relation'], 'opposite_directions')
            self.assertIn('straight intention recorded',
                          report['opposite_direction_left_turn_exception_judgment'])
            rows = [json.loads(line) for line in
                    (root / 'crossing_history.jsonl').read_text().splitlines()]
            rows[0]['other_left_turn_intended'] = True
            (root / 'crossing_history.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'straight intention missing'):
                analyzer.analyze(root)

    def test_bundle_binds_separate_sources(self):
        construction = json.loads((HERE / 'straight-construction.json').read_text())
        self.assertTrue(construction['case_id'].endswith('stop_opposite_straight'))
        for item in construction['files']:
            source = item.get('source')
            if source and source.startswith('work/'):
                self.assertEqual(item['content'],
                                 (HERE.parents[1] / source).read_text())


if __name__ == '__main__':
    unittest.main()
