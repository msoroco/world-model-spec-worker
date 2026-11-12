import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lamp_source_capture import LampSourceRecorder
from backup_lamp_measurement import measure


class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Transform:
    def get_forward_vector(self):
        return Vector(1, 0)


class Ego:
    id = 42
    state = 0

    def get_transform(self):
        return Transform()

    def get_velocity(self):
        return Vector(3, 0)

    def get_light_state(self):
        return self.state


class LampSourceCaptureTests(unittest.TestCase):
    def test_retains_native_state_and_original_motion(self):
        with TemporaryDirectory() as directory:
            ego = Ego()
            equipment = {'actor_id': 42, 'kind': 'motor_vehicle',
                         'blueprint_source_sha256': 'a' * 64,
                         'installed_backup_lamps': ['rear-left']}
            with LampSourceRecorder(directory, ego, equipment, 8) as recorder:
                first = recorder.append(100, 0)
                ego.state = 8
                second = recorder.append(101, 0.05)
                self.assertFalse(first['native_backup_lamp_bit'])
                self.assertTrue(second['native_backup_lamp_bit'])
                with self.assertRaisesRegex(ValueError, 'missing or unordered'):
                    recorder.append(103, 0.1)
            rows = [json.loads(line) for line in (Path(directory) / 'motion.jsonl').read_text().splitlines()]
            self.assertEqual([row['frame'] for row in rows], [100, 101])
            self.assertEqual(rows[1]['native_light_state_bits'], 8)
            frame_map = Path(directory) / 'video_frames.jsonl'
            frame_map.write_text(''.join(json.dumps({'video_frame': index,
                'carla_frame': row['frame'], 'time_s': row['time_s']}) + '\n'
                for index, row in enumerate(rows)))
            observed = measure(Path(directory) / 'motion.jsonl',
                               Path(directory) / 'equipment.json', frame_map)
            self.assertEqual(observed['forward_frames'], [100, 101])
            self.assertEqual(observed['forward_with_native_lamp_bit_frames'], [101])

    def test_rejects_unbound_equipment(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                LampSourceRecorder(directory, Ego(), {'actor_id': 99, 'kind': 'motor_vehicle'}, 8)


if __name__ == '__main__':
    unittest.main()
