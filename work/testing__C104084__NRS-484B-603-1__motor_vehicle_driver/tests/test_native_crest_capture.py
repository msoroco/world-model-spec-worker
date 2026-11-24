"""Original tick joins stay distinct from synthetic saved-fixture pixels."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_crest_capture import NativeTickRecorder


class NativeCaptureTests(unittest.TestCase):
    def recorder(self):
        return NativeTickRecorder(ego_actor_id='ego', other_actor_id='other',
                                  native_capture_ref='native-job-603')

    def add(self, recorder, index, **changes):
        world_frame = 100 + index
        ego = {'actor_id': 'ego', 'station_m': 230 + index * .05,
               'speed_mps': 10, 'body_clearance_m': 5,
               'source_ref': f'native-job-603:ego:{world_frame}'}
        other = {'actor_id': 'other', 'station_m': 300 - index * .05,
                 'source_ref': f'native-job-603:other:{world_frame}'}
        camera_frames = {name: SimpleNamespace(frame=world_frame)
                         for name in ('front', 'left', 'right', 'rear')}
        ego.update(changes.get('ego', {}))
        other.update(changes.get('other', {}))
        camera_frames.update(changes.get('cameras', {}))
        return recorder.append(world_frame=world_frame, ego=ego, other=other,
                               camera_frames=camera_frames)

    def test_complete_original_tick_sources(self):
        recorder = self.recorder()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, '900-frame'):
                recorder.write(temp)
            for index in range(900):
                self.add(recorder, index)
            receipt = recorder.write(temp)
            self.assertEqual(receipt['frame_count'], 900)
            rows = json.loads(Path(temp, 'motion.json').read_text())
            identities = [json.loads(line) for line in Path(temp, 'frame-map.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), len(identities))
            self.assertEqual(rows[-1]['frame_id'], identities[-1]['carla_frame'])
            self.assertEqual(identities[-1]['time_s'], 899 / 20)
            with self.assertRaisesRegex(ValueError, 'fresh'):
                recorder.write(temp)

    def test_rejects_desynchronized_camera_and_actor(self):
        recorder = self.recorder()
        with self.assertRaisesRegex(ValueError, 'camera'):
            self.add(recorder, 0, cameras={'rear': SimpleNamespace(frame=99)})
        self.assertEqual(recorder.motion, [])
        with self.assertRaisesRegex(ValueError, 'actor identity'):
            self.add(recorder, 0, ego={'actor_id': 'decoy'})
        with self.assertRaisesRegex(ValueError, 'source must identify'):
            self.add(recorder, 0, other={'source_ref': 'unbound'})
        self.add(recorder, 0)
        with self.assertRaisesRegex(ValueError, 'reversed'):
            self.add(recorder, 1, other={'station_m': 301})


if __name__ == '__main__':
    unittest.main()
