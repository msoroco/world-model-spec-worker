"""Check control phase isolation in the source-shaped CPU sweep."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_governing_law_sweep import ONSETS, SOURCE, construct  # noqa: E402
from control_phase_measurement import measure_red_onset  # noqa: E402


class GoverningLawSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = [json.loads(line) for line in
                      (SOURCE/'native-actors.jsonl').read_text().splitlines()]

    def test_only_control_phase_changes(self):
        for onset in ONSETS:
            sampled = construct(self.source, onset)
            self.assertEqual(len(sampled), 600)
            for i, (before, after) in enumerate(zip(self.source, sampled)):
                for key in before:
                    if key not in ('governing_control_state', 'scene_actor_inventory'):
                        self.assertEqual(after[key], before[key])
                state = 'TrafficLightState.Green' if i < onset else 'TrafficLightState.Red'
                self.assertEqual(after['governing_control_state']['control_state'], state)
                before_control = {k: v for k, v in before['governing_control_state'].items()
                                  if k != 'control_state'}
                after_control = {k: v for k, v in after['governing_control_state'].items()
                                 if k not in ('control_state', 'sweep_source_kind', 'red_onset_sample')}
                self.assertEqual(after_control, before_control)
                old_inventory = copy.deepcopy(before['scene_actor_inventory'])
                new_inventory = copy.deepcopy(after['scene_actor_inventory'])
                for inventory in (old_inventory, new_inventory):
                    next(a for a in inventory['actors'] if a['actor_id'] == 501).pop('state')
                self.assertEqual(old_inventory, new_inventory)

    def test_bad_setting_or_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            construct(self.source, 300)
        changed = copy.deepcopy(self.source)
        changed[1]['governing_control_state']['control_state'] = 'TrafficLightState.Green'
        with self.assertRaisesRegex(ValueError, 'changed'):
            construct(changed, ONSETS[0])
        changed = copy.deepcopy(self.source)
        changed[1]['scene_actor_inventory']['actors'] = []
        with self.assertRaisesRegex(ValueError, 'inventory'):
            construct(changed, ONSETS[0])

    def test_measured_phase_and_changed_identity(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=HERE.parents[1]/'.runtime-work') as folder:
            actor = Path(folder)/'native-actors.jsonl'
            mapping = SOURCE/'video_frames.jsonl'
            rows = construct(self.source, ONSETS[1])
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            phase = measure_red_onset(actor, mapping, expected_control_id=501,
                                      source_kind='synthetic_native_sample')
            self.assertEqual((phase['red_onset_sample'], phase['red_onset_s']), (220, 11.0))
            rows[220]['governing_control_state']['control_actor_id'] = 502
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'identity'):
                measure_red_onset(actor, mapping, expected_control_id=501,
                                  source_kind='synthetic_native_sample')


if __name__ == '__main__':
    unittest.main()
