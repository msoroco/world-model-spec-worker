import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup_lamp_measurement import measure


def write(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


class BackupLampMeasurementTests(unittest.TestCase):
    def test_forward_overlap_preserves_pixel_uncertainty(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            equipment = root / 'equipment.json'
            equipment.write_text(json.dumps({'kind': 'motor_vehicle', 'actor_id': 3,
                'blueprint_source_sha256': 'a' * 64, 'installed_backup_lamps': ['rear-left']}))
            motion = root / 'motion.jsonl'
            frames = root / 'video_frames.jsonl'
            rows = [{'frame': 10 + i, 'time_s': i / 20, 'actor_id': 3,
                     'heading_xy': [1, 0], 'velocity_xy_mps': [speed, 0],
                     'native_backup_lamp_bit': lit}
                    for i, (speed, lit) in enumerate([(-1, True), (1, False), (2, True)])]
            maps = [{'video_frame': i, 'carla_frame': row['frame'], 'time_s': row['time_s']}
                    for i, row in enumerate(rows)]
            write(motion, rows)
            write(frames, maps)
            value = measure(motion, equipment, frames)
            self.assertEqual(value['forward_frames'], [11, 12])
            self.assertEqual(value['forward_with_native_lamp_bit_frames'], [12])
            self.assertIsNone(value['actual_lamp_emission'])
            self.assertIsNone(value['legal_result'])
            rows[2]['actor_id'] = 9
            write(motion, rows)
            with self.assertRaisesRegex(ValueError, 'identity'):
                measure(motion, equipment, frames)

    def test_missing_lamp_readback_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            equipment = root / 'equipment.json'
            equipment.write_text(json.dumps({'kind': 'motor_vehicle', 'actor_id': 3,
                'blueprint_source_sha256': 'a' * 64, 'installed_backup_lamps': []}))
            motion = root / 'motion.jsonl'
            frames = root / 'video_frames.jsonl'
            write(motion, [{'frame': 1, 'time_s': 0, 'actor_id': 3,
                            'heading_xy': [1, 0], 'velocity_xy_mps': [1, 0]}])
            write(frames, [{'video_frame': 0, 'carla_frame': 1, 'time_s': 0}])
            with self.assertRaisesRegex(ValueError, 'state missing'):
                measure(motion, equipment, frames)


if __name__ == '__main__':
    unittest.main()
