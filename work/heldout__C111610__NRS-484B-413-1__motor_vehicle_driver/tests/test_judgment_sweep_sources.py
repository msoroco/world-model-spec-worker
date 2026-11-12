"""Construct source-shaped probes for the unexpanded judgment dimensions.

These probes test measurement sensitivity only. They are not selected cases or
evidence of physical audibility, affectedness, or reasonable safety.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('turn_measurement', ROOT / 'native_horn/turn_signal_measurement.py')
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
SOURCE_NAMES = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                'affected_participants.json', 'participant_bodies.jsonl')


class JudgmentSourceConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = json.loads((ROOT / 'pedestrian-horn-diagnostic.json').read_text())['files']

    def measure(self, changes=None):
        files = {name: self.originals[name] for name in SOURCE_NAMES}
        if changes:
            files.update(changes)
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name in SOURCE_NAMES:
                path = Path(directory) / name
                path.write_text(files[name])
                paths.append(path)
            return measurement.measure(*paths)

    def test_pedestrian_clearance_construction_changes_only_original_body_path(self):
        baseline = self.measure()
        rows = [json.loads(row) for row in self.originals['participant_bodies.jsonl'].splitlines()]
        for row in rows:
            row['bodies']['ped_listener']['y_m'] += 12.0
        shifted = self.measure({'participant_bodies.jsonl': ''.join(json.dumps(row) + '\n' for row in rows)})
        self.assertNotEqual(baseline['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m'],
                            shifted['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m'])
        self.assertNotEqual(baseline['sources']['participant_bodies.jsonl'], shifted['sources']['participant_bodies.jsonl'])
        for name in SOURCE_NAMES[:-1]:
            self.assertEqual(baseline['sources'][name], shifted['sources'][name])

    def test_vehicle_clearance_construction_changes_vehicle_measurement(self):
        baseline = self.measure()
        rows = [json.loads(row) for row in self.originals['participant_bodies.jsonl'].splitlines()]
        for row in rows:
            row['bodies']['affected_vehicle']['x_m'] = 5.0
            row['bodies']['affected_vehicle']['y_m'] = 5.0
        shifted = self.measure({'participant_bodies.jsonl': ''.join(json.dumps(row) + '\n' for row in rows)})
        self.assertNotEqual(baseline['participant_clearance']['affected_vehicle']['minimum_sampled_surface_gap_m'],
                            shifted['participant_clearance']['affected_vehicle']['minimum_sampled_surface_gap_m'])
        self.assertEqual(baseline['participant_clearance']['ped_listener'], shifted['participant_clearance']['ped_listener'])

    def test_listener_audio_construction_changes_measured_energy_without_legal_label(self):
        baseline = self.measure()
        rows = [json.loads(row) for row in self.originals['ego_signal_audio.jsonl'].splitlines()]
        for row in rows:
            if row['listener_audio_samples'] is not None:
                row['listener_audio_samples'] = [0.1] * len(row['listener_audio_samples'])
        changed = self.measure({'ego_signal_audio.jsonl': ''.join(json.dumps(row) + '\n' for row in rows)})
        self.assertNotEqual(baseline['max_pre_turn_listener_audio_rms'], changed['max_pre_turn_listener_audio_rms'])
        self.assertIsNone(changed['clearly_audible_legal_judgment'])
        for name in ('ego_turn_motion.jsonl', 'affected_participants.json', 'participant_bodies.jsonl'):
            self.assertEqual(baseline['sources'][name], changed['sources'][name])


if __name__ == '__main__':
    unittest.main()
