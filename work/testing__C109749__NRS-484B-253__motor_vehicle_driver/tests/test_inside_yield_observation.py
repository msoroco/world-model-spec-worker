import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('inside_yield_observation', ROOT / 'inside_yield_observation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(root, *, initial_inside=True, indicator=True):
    files = json.loads((ROOT / 'diagnostic.json').read_text())['files']
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        (root / name).write_text(files[name])
    rows = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines() if line]
    if initial_inside:
        rows[0]['oncoming']['position_xy_m'] = rows[1]['oncoming']['position_xy_m']
        rows[0]['oncoming']['body_vertices_xy_m'] = rows[1]['oncoming']['body_vertices_xy_m']
    if not indicator:
        rows[2]['ego_left_indicator'] = False
    (root / 'interaction_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


class InsideYieldObservationTests(unittest.TestCase):
    def test_sources_show_initial_inside_actor_then_subject_yield_and_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            result = module.observe(root)
            self.assertEqual(result['subject_yield_frames'], [38035])
            self.assertLess(result['initial_oncoming_clearance_frame'], result['ego_turn_start_frame'])
            self.assertFalse(result['legal_verdict_asserted'])
            self.assertFalse(result['physical_acceptance_claimed'])

    def test_rejects_outside_initial_body_and_missing_yield_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, initial_inside=False)
            with self.assertRaisesRegex(ValueError, 'Initial opposing complete body'):
                module.observe(root)
            fixture(root, indicator=False)
            with self.assertRaisesRegex(ValueError, 'No sourced subject yield'):
                module.observe(root)
