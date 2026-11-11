import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_signal_measurement import measure


def write(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


class TurnSignalSourceTests(unittest.TestCase):
    def test_timing_keeps_audibility_and_effect_unknown(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            motion, signals, frames = [root / name for name in
                                       ('motion.jsonl', 'signals.jsonl', 'frames.jsonl')]
            context = root / 'context.json'
            context.write_text(json.dumps({'highway_source': 'map-hash',
                'turn_route_source': 'route-hash',
                'pedestrian': {'position_motion_source': 'pedestrian-hash'}}))
            moves = [{'frame': i + 20, 'time_s': i / 20,
                      'turning_from_direct_course': i == 2} for i in range(3)]
            states = [{'frame': i + 20, 'time_s': i / 20,
                       'horn_command': i == 1, 'native_indicator_state': i > 0}
                      for i in range(3)]
            maps = [{'video_frame': i, 'carla_frame': i + 20, 'time_s': i / 20}
                    for i in range(3)]
            write(motion, moves); write(signals, states); write(frames, maps)
            value = measure(motion, signals, frames, context)
            self.assertEqual(value['turn_onset_frame'], 22)
            self.assertEqual(value['horn_command_before_turn_frames'], [21])
            self.assertIsNone(value['horn_audible_at_pedestrian'])
            self.assertIsNone(value['possible_effect']['pedestrian'])
            states[1]['frame'] = 99
            write(signals, states)
            with self.assertRaisesRegex(ValueError, 'frame join'):
                measure(motion, signals, frames, context)

    def test_uncited_user_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / name for name in ('motion.jsonl', 'signals.jsonl', 'frames.jsonl')]
            write(files[0], [{'frame': 1, 'time_s': 0, 'turning_from_direct_course': True}])
            write(files[1], [{'frame': 1, 'time_s': 0, 'horn_command': False,
                              'native_indicator_state': False}])
            write(files[2], [{'video_frame': 0, 'carla_frame': 1, 'time_s': 0}])
            context = root / 'context.json'
            context.write_text(json.dumps({'highway_source': 'map', 'turn_route_source': 'route',
                                           'pedestrian': {}}))
            with self.assertRaisesRegex(ValueError, 'independent'):
                measure(*files, context)


if __name__ == '__main__':
    unittest.main()
