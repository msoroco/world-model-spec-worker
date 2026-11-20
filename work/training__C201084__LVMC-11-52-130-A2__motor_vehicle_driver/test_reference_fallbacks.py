"""Check candidate tuning reaches the Native control calls at the full clock."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from native_capture import acquire
from test_native_capture import ego, follower, plan

HERE = Path(__file__).resolve().parent


class FallbackTests(unittest.TestCase):
    def test_distinct_candidate_controls_keep_600_frame_capture(self):
        manifest = json.loads((HERE/'draft-reference-fallback-manifest.json').read_text())
        candidates = manifest['cases'][0]['candidates']
        self.assertEqual([row['id'] for row in candidates],
                         ['fallback1', 'fallback2', 'fallback3'])
        seen = set()
        for candidate in candidates:
            construction = json.loads((HERE/candidate['construction']).read_text())
            config = json.loads(next(row['content'] for row in construction['files']
                                     if row['path'] == 'config.json'))
            tuning = config['controller_tuning']
            self.assertEqual(config['candidate_id'], candidate['id'])
            seen.add(tuple(sorted(tuning.items())))
            p = plan()
            p['controller_tuning'] = tuning
            callback = []
            current = [0]
            def install(world, carla, actor, receive):
                callback.append(receive)
                return [SimpleNamespace(stop=lambda: None, destroy=lambda: None)]
            def tick():
                current[0] += 1
                for name in p['camera_names']:
                    callback[0](name, SimpleNamespace(frame=current[0]))
                return current[0]
            class Sink:
                def __init__(self, path, width, height):
                    pass
                def write(self, image):
                    pass
                def close(self):
                    pass
            world = SimpleNamespace(
                get_settings=lambda: SimpleNamespace(synchronous_mode=True,
                                                     fixed_delta_seconds=0.05),
                tick=tick,
                get_snapshot=lambda: SimpleNamespace(timestamp=SimpleNamespace(
                    elapsed_seconds=(current[0]-1)/20)))
            follower_controls = []
            trailing = follower()
            trailing.apply_control = follower_controls.append
            calls = []
            def control(actor, carla, target, **kwargs):
                calls.append(kwargs)
                return {'phase': 'diagnostic'}
            carla = SimpleNamespace(VehicleControl=lambda **kw: kw)
            with tempfile.TemporaryDirectory() as tmp, \
                 patch('native_capture.apply', side_effect=control), \
                 patch('native_capture.sample_native', return_value={}):
                result = acquire(world, carla, ego(), trailing, None, p,
                                 'reference', Path(tmp), sink_factory=Sink,
                                 camera_installer=install)
                self.assertEqual(result['source_frames'], 600)
                self.assertEqual(len((Path(tmp)/'native-actors.jsonl').read_text().splitlines()), 600)
            self.assertEqual(len(calls), 600)
            self.assertEqual(calls[0], {key: tuning[key] for key in
                             ('stop_radius_m', 'cruise_mps', 'deceleration_mps2')})
            self.assertEqual(len(follower_controls), 600)
            self.assertEqual(follower_controls[0]['brake'],
                             1.0 if 12 < tuning['following_brake_gap_m'] else 0.0)
            self.assertEqual(follower_controls[0]['throttle'],
                             0.0 if 12 < tuning['following_brake_gap_m'] else
                             tuning['following_cruise_throttle'])
        self.assertEqual(len(seen), 3)


if __name__ == '__main__':
    unittest.main()
