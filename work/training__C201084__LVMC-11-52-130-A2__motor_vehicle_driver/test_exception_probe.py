"""CPU checks for source-bound lead conflict construction."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from exception_capture import sample_lead
from exception_measurement import analyze
from exception_runner import run

HERE = Path(__file__).resolve().parent


def location(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


def environment(*, lead_road=17):
    sign = SimpleNamespace(id=101, type_id='static.prop.fire_lane_sign',
        get_transform=lambda: SimpleNamespace(location=location(6, -1)))
    def waypoint(point, **kwargs):
        road = lead_road if point.x == 18 else 17
        return SimpleNamespace(road_id=road, lane_id=-1,
            transform=SimpleNamespace(location=location(point.x, point.y)))
    mapping = SimpleNamespace(name='TownFireLane', get_waypoint=waypoint)
    spawned = []
    def spawn(blueprint, transform):
        actor = SimpleNamespace(id=100+len(spawned),
                                destroy=lambda: spawned.append('destroy'))
        spawned.append(blueprint)
        return actor
    world = SimpleNamespace(get_map=lambda: mapping,
        get_actors=lambda: SimpleNamespace(find=lambda ident: sign if ident == 101 else None),
        get_blueprint_library=lambda: SimpleNamespace(find=lambda name: name),
        try_spawn_actor=spawn)
    carla = SimpleNamespace(
        Location=lambda **kwargs: SimpleNamespace(**kwargs),
        Rotation=lambda **kwargs: SimpleNamespace(**kwargs),
        Transform=lambda loc, rot: SimpleNamespace(location=loc, rotation=rot),
        LaneType=SimpleNamespace(Driving=1))
    return SimpleNamespace(get_world=lambda: world), carla, spawned


class ExceptionProbeTests(unittest.TestCase):
    def survey(self):
        survey = json.loads((HERE/'draft-conflict-survey.json').read_text())
        survey['map_name'] = 'TownFireLane'
        return survey

    def test_runner_binds_retained_lead_and_cameras(self):
        client, carla, spawned = environment()
        tuning = {'same_path_half_width_m': 1.8, 'stop_gap_m': 8.0,
                  'deceleration_mps2': 3.0, 'cruise_throttle': 0.28}
        def capture(world, carla, ego, follower, lead, sign, plan, attempt):
            self.assertEqual([ego.id, follower.id, lead.id], [100, 101, 102])
            self.assertEqual(plan['capture_frames'], 600)
            self.assertEqual(len(plan['camera_names']), 4)
            self.assertFalse(plan['conflict_probe']['statutory_necessity_verified'])
            self.assertEqual(plan['conflict_controller_tuning'], tuning)
            return {'source_frames': 600, 'physical_completion_claimed': False}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'attempt'
            result = run(client, carla, self.survey(), path, acquisition=capture,
                         controller_tuning=tuning,
                         processor=lambda _: {
                             'physical_or_legal_completion_claimed': False,
                             'statutory_necessity_verified': False})
            self.assertEqual(result['lead_actor_id'], 102)
            self.assertFalse(result['physical_or_legal_completion_claimed'])
            self.assertTrue((path/'native-survey-readback.json').is_file())
            self.assertTrue((path/'acquisition-provenance.json').is_file())
            self.assertTrue((path/'source-measurement.json').is_file())
        self.assertEqual(spawned[-3:], ['destroy']*3)

    def test_wrong_lead_road_rejected_before_spawn(self):
        client, carla, spawned = environment(lead_road=19)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Lead spawn differs'):
                run(client, carla, self.survey(), Path(tmp)/'attempt')
        self.assertEqual(spawned, [])

    def test_materialized_bundle_directory_accepted_but_prior_source_preserved(self):
        client, carla, _ = environment()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'attempt'
            path.mkdir()
            (path/'config.json').write_text('{}')
            (path/'runner.py').write_text('')
            (path/'construction.json').write_text(json.dumps({
                'files': [{'path': 'runner.py'}, {'path': 'config.json'}]}))
            run(client, carla, self.survey(), path,
                acquisition=lambda *args: {'source_frames': 600},
                processor=lambda _: {
                    'physical_or_legal_completion_claimed': False,
                    'statutory_necessity_verified': False})
            self.assertTrue((path/'source-measurement.json').is_file())
            with self.assertRaisesRegex(ValueError, 'Retain previous attempt'):
                run(client, carla, self.survey(), path)

    def test_three_candidate_tunings_reach_native_capture(self):
        observed = []
        for ident in ('fallback1', 'fallback2', 'fallback3'):
            construction = json.loads((HERE/f'draft-conflict-{ident}-construction.json').read_text())
            config = json.loads(next(row['content'] for row in construction['files']
                                     if row['path'] == 'config.json'))
            tuning = config['conflict_controller_tuning']
            client, carla, _ = environment()
            with tempfile.TemporaryDirectory() as tmp:
                def capture(world, carla, ego, follower, lead, sign, plan, attempt):
                    self.assertEqual(plan['conflict_controller_tuning'], tuning)
                    return {'source_frames': 600}
                run(client, carla, self.survey(), Path(tmp)/ident,
                    acquisition=capture, controller_tuning=tuning,
                    processor=lambda _: {
                        'physical_or_legal_completion_claimed': False,
                        'statutory_necessity_verified': False})
            observed.append(json.dumps(tuning, sort_keys=True))
        self.assertEqual(len(set(observed)), 3)

    def test_sample_lead_requires_same_road_and_body(self):
        transform = SimpleNamespace(location=location(18, 1),
                                    rotation=SimpleNamespace(yaw=0))
        lead = SimpleNamespace(id=77, get_transform=lambda: transform,
            get_velocity=lambda: location(0, 0),
            bounding_box=SimpleNamespace(get_world_vertices=lambda _: [
                location(17, 0), location(19, 0), location(19, 2), location(17, 2)]))
        client, carla, _ = environment()
        row = sample_lead(client.get_world(), carla, lead,
                          {'fixed_context': {'road_id': 17}})
        self.assertEqual(row['lead_actor_id'], 77)
        self.assertEqual(len(row['lead_body_vertices_xyz_m']), 4)
        wrong, _, _ = environment(lead_road=19)
        with self.assertRaisesRegex(ValueError, 'lead vehicle departed'):
            sample_lead(wrong.get_world(), carla, lead,
                        {'fixed_context': {'road_id': 17}})

    def test_saved_source_remeasures_lead_and_rejects_identity_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            plan = {'fixed_context': {'road_id': 17}, 'conflict_probe': {
                'statutory_necessity_verified': False,
                'original_review_required': True}}
            (attempt/'native-survey-readback.json').write_text(json.dumps(plan))
            stop = {'frames': 2, 'samples': [
                {'carla_frame': 1, 'time_s': 0.0, 'speed_mps': 2.0,
                 'body_zone_overlap_m2': 0.5},
                {'carla_frame': 2, 'time_s': 0.05, 'speed_mps': 0.0,
                 'body_zone_overlap_m2': 0.5}],
                'source_kind': 'synthetic_native_sample', 'ego_actor_id': 41,
                'actor_source_sha256': 'actor', 'frame_map_sha256': 'frame',
                'survey_readback_sha256': 'survey', 'source_camera_videos': {},
                'near_zero_with_zone_overlap_frames': 1}
            rows = []
            for frame in (1, 2):
                row = dict(frame=frame, ego_actor_id=41, following_actor_id=42,
                    ego_pose_xyz_m=[10, 1, 0], ego_yaw_deg=0,
                    ego_velocity_xyz_mps=[0, 0, 0],
                    lead_actor_id=77, lead_road_id=17, lead_lane_id=-1,
                    lead_pose_xyz_m=[18, 1, 0], lead_yaw_deg=0,
                    lead_velocity_xyz_mps=[0, 0, 0],
                    lead_body_vertices_xyz_m=[[17, 0, 0], [19, 0, 0],
                                              [19, 2, 0], [17, 2, 0]],
                    requested_control={'brake': 1.0},
                    physical_completion_claimed=False,
                    statutory_necessity_claimed=False)
                rows.append(row)
            actor_path = attempt/'native-actors.jsonl'
            actor_path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with patch('exception_measurement.analyze_stop', return_value=stop):
                result = analyze(attempt, diagnostic=True)
                self.assertEqual(result['frames'], 2)
                self.assertEqual(result['lead_ahead_frames'], 2)
                self.assertEqual(result['brake_request_frames'], 2)
                self.assertFalse(result['statutory_necessity_verified'])
                rows[1]['lead_actor_id'] = 78
                actor_path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
                with self.assertRaisesRegex(ValueError, 'lead actor identity changed'):
                    analyze(attempt, diagnostic=True)


if __name__ == '__main__':
    unittest.main()
