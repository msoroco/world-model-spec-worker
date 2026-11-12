"""Source-shaped synthetic probes for the far-approach observation contract."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from far_approach_observation import observe


def materialize(root, change=None):
    source = Path(__file__).with_name('source_fixture.json')
    files = json.loads(source.read_text())
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        (root / name).write_text(files[name])
    (root / 'config.json').write_text((ROOT / 'config.json').read_text())
    rows = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines() if line]
    for row in rows:
        actor = row['oncoming']
        actor['position_xy_m'][0] += 20
        for vertex in actor['body_vertices_xy_m']:
            vertex[0] += 20
        actor['velocity_xy_mps'] = [-1.0, 0.0]
    if change:
        change(rows)
    (root / 'interaction_history.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows))


class FarApproachObservationTests(unittest.TestCase):
    def test_turn_before_complete_opposing_body_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(root)
            observed = observe(root)
            self.assertEqual(observed['ego_turn_start_frame'], 38039)
            self.assertGreater(observed['opposing_entry_frame'], 38039)
            self.assertGreaterEqual(observed['turn_sample']['kinematic_time_to_conflict_s'], 4.0)
            self.assertFalse(observed['legal_verdict_asserted'])

    def test_rejects_close_approach_and_missing_turn_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(root, lambda rows: [r['oncoming'].update(velocity_xy_mps=[-4.0, 0.0]) for r in rows])
            with self.assertRaisesRegex(ValueError, 'engineering release TTC'):
                observe(root)
            materialize(root, lambda rows: rows[6].update(ego_left_indicator=False))
            with self.assertRaisesRegex(ValueError, 'Left indicator'):
                observe(root)


if __name__ == '__main__':
    unittest.main()
