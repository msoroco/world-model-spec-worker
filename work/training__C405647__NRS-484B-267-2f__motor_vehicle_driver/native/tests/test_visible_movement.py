"""Construction and source measurement for the unselected movement draft."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[2]
TMP = HERE.parents[1] / '.runtime-work/c405647-267-2f/tmp'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisibleMovementDraft(unittest.TestCase):
    def test_native_request_phases(self):
        runner = load('visible_runner', 'native/visible_movement_runner.py')
        config = {'requested_preparation_movement_mps': .5,
                  'requested_subsequent_emergency_speed_mps': 2}
        self.assertEqual([runner.source_motion_request(i, config) for i in (79, 80, 99, 100)],
                         [0.0, -.5, -.5, -2])

    def test_source_transition_and_missing_movement(self):
        measure = load('visible_measure', 'native/measure_visible_movement.py')
        source = HERE / 'draft-visible/source'
        observed = measure.measure(source)
        self.assertEqual(observed['preparation_movement_start_frame'], 80)
        self.assertFalse(observed['preparation_visibility_verified'])
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json'):
                shutil.copyfile(source / name, target / name)
            poses = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
            for index in range(80, 100):
                poses[index]['emergency']['speed_mps'] = 0
                poses[index]['emergency']['velocity_x_mps'] = 0
            (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(pose) + '\n' for pose in poses))
            # This negative isolates the indicator, so rehash the deliberately
            # changed diagnostic source before measuring it.
            import hashlib
            context = json.loads((target / 'emergency_context.json').read_text())
            context['native_source_hashes']['vehicle_poses.jsonl'] = hashlib.sha256((target / 'vehicle_poses.jsonl').read_bytes()).hexdigest()
            (target / 'emergency_context.json').write_text(json.dumps(context) + '\n')
            with self.assertRaisesRegex(ValueError, 'Subsequent emergency approach'):
                measure.measure(target)


if __name__ == '__main__':
    unittest.main()
