import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('c125697_finalizer', ROOT / 'finalizer.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)
fixture_spec = importlib.util.spec_from_file_location(
    'c125697_entry_fixture', Path(__file__).with_name('test_simultaneous_entries.py'))
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)


def build(root):
    root.mkdir()
    fixture.EntryTests().fixture(root)
    ctx_path = root / 'junction_context.json'
    ctx = json.loads(ctx_path.read_text())
    ctx['physical_acceptance_claimed'] = False
    ctx_path.write_text(json.dumps(ctx))
    history_path = root / 'crossing_history.jsonl'
    rows = [json.loads(line) for line in history_path.read_text().splitlines()]
    for row in rows:
        row['ego_vertices_m'] = row['ego']['body_vertices_xy_m']
    history_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (root / 'config.json').write_text(json.dumps({
        'law_id': 'NRS-484B-250-2', 'cell_id': 'C125697',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 45,
        'selected_case_id': finalizer.PRIMARY,
        'recording_description': {'purpose': 'synthetic finalizer source fixture'}}))
    (root / 'trace.jsonl').write_text(''.join(json.dumps({'frame': row['frame'],
        'time_s': row['time_s']}) + '\n' for row in rows))
    (root / 'capture').mkdir()
    (root / 'capture/evidence.jsonl').write_text('{}\n')
    for name in finalizer.CAMERAS:
        (root / name).write_bytes(b'fixture-only-placeholder')


class FinalizerTests(unittest.TestCase):
    def test_saved_original_sources_create_result_and_channels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attempt = root / 'attempt'
            build(attempt)
            output = root / 'analysis.json'
            measured = finalizer.finalize(attempt, output)
            self.assertAlmostEqual(measured['absolute_entry_time_difference_s'], .05)
            self.assertTrue(measured['other_spatially_right_of_ego_approach'])
            self.assertEqual(measured['right_of_way_judgment'], 'unresolved')
            result = json.loads((attempt / 'result.json').read_text())
            self.assertEqual(result['case_id'], finalizer.PRIMARY)
            self.assertFalse(result['target_checks'][0]['physical_cause_confirmed'])
            self.assertEqual(len((attempt / 'channels/entry_timing.jsonl').read_text().splitlines()), 3)
            self.assertFalse(json.loads(output.read_text())['physical_acceptance_claimed'])

    def test_missing_source_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / 'missing'
            build(missing)
            (missing / 'overview.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'overview.mkv'):
                finalizer.finalize(missing, root / 'missing-output.json')
            stale = root / 'stale'
            build(stale)
            frames = [json.loads(line) for line in (stale / 'video_frames.jsonl').read_text().splitlines()]
            frames[1]['carla_frame'] = 999
            (stale / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
            with self.assertRaisesRegex(ValueError, 'frame join'):
                finalizer.finalize(stale, root / 'stale-output.json')


if __name__ == '__main__':
    unittest.main()
