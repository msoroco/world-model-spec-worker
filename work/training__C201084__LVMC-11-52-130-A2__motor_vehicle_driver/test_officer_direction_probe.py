"""CPU tests for the retained officer-actor source path."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from officer_direction_capture import acquire
from officer_direction_probe import (check_saved_officer_rows,
                                     inspect_officer, sample_officer)
from officer_direction_runner import finalize_officer, run


def point(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class OfficerProbeTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=501, type_id='walker.pedestrian.001',
            get_transform=lambda: SimpleNamespace(location=point(11, 1),
                                                  rotation=SimpleNamespace(yaw=90)),
            get_velocity=lambda: point(0, 0))
        world = SimpleNamespace(get_actors=lambda: SimpleNamespace(
            find=lambda ident: actor if ident == 501 else None))
        survey = {'police_officer': {'actor_id': 501, 'position_xy_m': [11, 1]}}
        return actor, world, survey

    def test_full_source_and_negative_identity_or_authority(self):
        actor, world, survey = self.fixture()
        readback = inspect_officer(world, survey)
        frames = [{'frame': i+20} for i in range(600)]
        rows = [dict(sample_officer(actor, readback, row['frame']),
                     video_frame=i) for i, row in enumerate(frames)]
        measured = check_saved_officer_rows(rows, frames, readback)
        self.assertEqual(measured['source_frames'], 600)
        self.assertFalse(measured['police_authority_verified'])
        rows[4]['police_authority_verified'] = True
        with self.assertRaisesRegex(ValueError, 'overclaims'):
            check_saved_officer_rows(rows, frames, readback)
        rows[4]['police_authority_verified'] = False
        rows[4]['officer_actor_id'] = 999
        with self.assertRaisesRegex(ValueError, 'source differs'):
            check_saved_officer_rows(rows, frames, readback)
        survey['police_officer']['actor_id'] = 999
        with self.assertRaisesRegex(ValueError, 'actor missing'):
            inspect_officer(world, survey)

    def test_four_camera_native_capture_and_hashed_finalizer(self):
        actor, world, survey = self.fixture()
        readback = inspect_officer(world, survey)
        plan = {'capture_hz': 20, 'capture_frames': 600,
                'camera_names': ['overview', 'approach', 'reference_corner',
                                 'driver_reference'],
                'police_officer_readback': readback}
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            (attempt/'officer-survey-readback.json').write_text(json.dumps(readback))
            def base_acquire(world, carla, ego, follower, sign, plan, case,
                             path, *, frame_map_factory):
                self.assertEqual(case, 'reference')
                fmap = frame_map_factory(path/'video_frames.jsonl')
                for i in range(600):
                    fmap.append(i+100, i/20)
                fmap.close()
                return {}
            result = acquire(world, None, None, None, None, actor, plan,
                             attempt, base_acquire=base_acquire)
            self.assertEqual(result['officer_measurement']['source_frames'], 600)
            measured = finalize_officer(attempt)
            self.assertEqual(len(measured['source_sha256']), 3)
            self.assertFalse(measured['physical_or_legal_completion_claimed'])

    def test_runner_binds_original_actor_and_remeasures(self):
        actor, world, survey = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            def reference_runner(client, carla, survey, case, path, *,
                                 acquisition, controller_tuning):
                self.assertEqual(case, 'reference')
                self.assertIsNone(controller_tuning)
                return acquisition(world, carla, None, None, None, {},
                                   case, path)
            def officer_capture(world, carla, ego, follower, sign, officer,
                                plan, path):
                self.assertIs(officer, actor)
                readback = plan['police_officer_readback']
                with (path/'video_frames.jsonl').open('x') as frames, \
                     (path/'police-officer-actor.jsonl').open('x') as rows:
                    for i in range(600):
                        frames.write(json.dumps({'carla_frame': i})+'\n')
                        rows.write(json.dumps(dict(sample_officer(
                            actor, readback, i), video_frame=i))+'\n')
                return {}
            result = run(None, None, survey, attempt,
                         reference_runner=reference_runner,
                         officer_capture=officer_capture)
            self.assertFalse(result['police_authority_verified'])
            self.assertEqual(json.loads((attempt/result[
                'officer_source_measurement']).read_text())['source_frames'], 600)


if __name__ == '__main__':
    unittest.main()
