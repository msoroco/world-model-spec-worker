import unittest
from types import SimpleNamespace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from aggressive_sequence import MILE_M, measure_sequence
from paved_boundary import mapped_right_edges, signed_clearance
from right_pass_source import candidates
from runner import check_config
from two_pass_finalizer import analyze
from two_pass_construction import PHASES, phase_at, transition_guard, validate_schedule


def sample(distance_m):
    return [{"frame": i, "time_s": i * .05, "driver_id": "ego-driver",
             "x_m": i * distance_m / 6, "y_m": 0} for i in range(7)]


def episodes():
    return [{"start_frame": start, "end_frame": end, "target_vehicle_id": 9,
             "before_gap_m": -2, "after_gap_m": 2,
             "rightward_separation_m": 1, "off_pavement_frames": [end]}
            for start, end in ((1, 2), (4, 5))]


class SequenceTests(unittest.TestCase):
    def test_exact_runner_config_and_saved_original_source_analysis(self):
        config_path=Path(__file__).parent/'config.json'
        if not config_path.is_file():
            config_path=Path(__file__).parent.parent/'config.json'
        config=json.loads(config_path.read_text())
        self.assertTrue(check_config(config).endswith('__repeated_right_pass'))
        wrong=dict(config,cell_id='C228508')
        with self.assertRaisesRegex(ValueError,'identity'):
            check_config(wrong)
        phases=['approach','first_right_pass_request','first_right_pass_request',
                'first_reentry','lead_reclaim_request','second_reentry',
                'second_right_pass_request','second_right_pass_request','exit']
        gaps=[-10,-10,10,10,-10,-10,-10,10,10]
        edge=[-1,1,1,-1,1,-1,1,1,-1]
        with TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'config.json').write_text(json.dumps(config))
            files={'video_frames.jsonl':[], 'driving_trace.jsonl':[],
                   'following_sources.jsonl':[], 'right_pass_sources.jsonl':[]}
            for i in range(9):
                time_s=i*.05
                ego_x=i*10+gaps[i]
                ego_y=-4-edge[i]
                lead_x=i*10
                files['video_frames.jsonl'].append({'video_frame':i,'carla_frame':i,'time_s':time_s})
                files['driving_trace.jsonl'].append({'frame':i,'time_s':time_s,
                    'driver_id':'ego-actor-1','x_m':ego_x,'y_m':ego_y})
                files['following_sources.jsonl'].append({'frame':i,'time_s':time_s,
                    'ego':{'actor_id':1,'position_m':[ego_x,ego_y,0]},
                    'lead':{'actor_id':2,'position_m':[lead_x,0,0]}})
                files['right_pass_sources.jsonl'].append({'frame':i,'time_s':time_s,
                    'ego_actor_id':1,'fixed_overtaken_actor_id':2,
                    'ego_station_m':ego_x,'lead_station_m':lead_x,
                    'ego_xy_m':[ego_x,ego_y],'lead_xy_m':[lead_x,0],
                    'right_of_mapped_road_edge_m':edge[i],
                    'mapped_driving_edge_xy_m':[0,-2],
                    'mapped_road_edge_xy_m':[0,-4],
                    'right_axis_xy':[0,-1],
                    'requested_phase':phases[i]})
            for name,rows in files.items():
                (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
            for name in ('overview','approach','reference_corner','driver_reference'):
                (root/(name+'.mkv')).write_bytes(b'synthetic camera source')
            report=analyze(root)
            observation=report['measurements']['two_right_pass_observation']['value']
            self.assertEqual(observation['source_status'],'candidate')
            self.assertEqual(observation['event_envelope']['right_passing_episode_count'],2)
            self.assertFalse(observation['right_pass_violation_decided'])
            (root/'right_pass_sources.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                analyze(root)

    def test_two_original_passes_require_same_vehicle_reentry_and_frame_join(self):
        phases = ['approach','first_right_pass_request','first_right_pass_request',
                  'first_reentry','lead_reclaim_request','second_reentry',
                  'second_right_pass_request','second_right_pass_request','exit']
        gaps = [-10,-10,10,10,-10,-10,-10,10,10]
        edge = [-1,1,1,-1,1,-1,1,1,-1]
        rows = [{'frame':i,'time_s':i*.05,'ego_actor_id':1,
                 'fixed_overtaken_actor_id':2,'ego_station_m':i*10+gaps[i],
                 'lead_station_m':i*10,'right_of_mapped_road_edge_m':edge[i],
                 'mapped_driving_edge_xy_m':[0,-2],
                 'mapped_road_edge_xy_m':[0,-4],
                 'requested_phase':phases[i]} for i in range(9)]
        frames = [{'carla_frame':i,'time_s':i*.05} for i in range(9)]
        proof = candidates(rows,frames)
        self.assertEqual(proof['status'],'candidate')
        self.assertEqual(len(proof['episodes']),2)
        self.assertEqual({x['target_vehicle_id'] for x in proof['episodes']},{2})
        self.assertFalse(proof['pavement_surface_decided'])
        wrong_frame = [dict(x) for x in frames]
        wrong_frame[4]['carla_frame'] = 99
        with self.assertRaisesRegex(ValueError,'frame join'):
            candidates(rows,wrong_frame)
        wrong_actor = [dict(x) for x in rows]
        wrong_actor[7]['fixed_overtaken_actor_id'] = 3
        with self.assertRaisesRegex(ValueError,'identity'):
            candidates(wrong_actor,frames)
        no_reentry = [dict(x) for x in rows]
        for i in (3,4,5):no_reentry[i]['right_of_mapped_road_edge_m']=1
        self.assertIn('reentry',candidates(no_reentry,frames)['reason'])
        no_reclaim = [dict(x) for x in rows]
        for i in (3,4,5):no_reclaim[i]['ego_station_m']=no_reclaim[i]['lead_station_m']+10
        self.assertIn('reclaim',candidates(no_reclaim,frames)['reason'])

    def test_mapped_driving_and_shoulder_edges_are_retained_separately(self):
        def lane(lane_id, y, width, lane_type, neighbor=None):
            waypoint = SimpleNamespace(road_id=7, lane_id=lane_id,
                lane_width=width, lane_type=lane_type,
                transform=SimpleNamespace(rotation=SimpleNamespace(yaw=0),
                                          location=SimpleNamespace(x=0, y=y)))
            waypoint.get_right_lane = lambda: neighbor
            return waypoint
        shoulder = lane(-2, -3, 2, 'Shoulder')
        driving = lane(-1, 0, 4, 'Driving', shoulder)
        geometry = mapped_right_edges(driving)
        self.assertEqual(geometry['driving_edge_xy_m'], (0, -2))
        self.assertEqual(geometry['mapped_road_edge_xy_m'], (0, -4))
        self.assertEqual(geometry['target_xy_m'], (0, -5.5))
        self.assertEqual(geometry['shoulder_lane_id'], -2)
        self.assertTrue(geometry['pavement_surface_review_required'])
        self.assertGreater(signed_clearance(SimpleNamespace(x=0, y=-5),
                           geometry['mapped_road_edge_xy_m'], geometry['right_axis_xy']), 0)
        without_shoulder = mapped_right_edges(lane(-1, 0, 4, 'Driving'))
        self.assertIsNone(without_shoulder['shoulder_lane_id'])
        self.assertEqual(without_shoulder['mapped_road_edge_xy_m'], (0, -2))

    def test_two_pass_requests_have_reentry_and_original_geometry_guards(self):
        self.assertTrue(validate_schedule())
        self.assertEqual(phase_at(300).name, 'first_right_pass_request')
        self.assertEqual(phase_at(480).name, 'first_reentry')
        self.assertEqual(phase_at(540).name, 'lead_reclaim_request')
        self.assertEqual(phase_at(620).name, 'second_reentry')
        self.assertEqual(phase_at(750).name, 'second_right_pass_request')
        self.assertEqual(PHASES[1].ego_target, 'right_of_paved_edge')
        self.assertEqual(PHASES[3].ego_speed_mps, 6)
        self.assertGreater(PHASES[3].lead_speed_mps, PHASES[3].ego_speed_mps)
        nominal_to_second_pass_s = sum((p.end_m-p.start_m)/p.ego_speed_mps for p in PHASES[:-1])
        self.assertLess(nominal_to_second_pass_s, 60)
        first_gain_m = (PHASES[1].ego_speed_mps-PHASES[1].lead_speed_mps) * (PHASES[1].end_m-PHASES[1].start_m)/PHASES[1].ego_speed_mps
        reclaim_gain_m = (PHASES[3].lead_speed_mps-PHASES[3].ego_speed_mps) * (PHASES[3].end_m-PHASES[3].start_m)/PHASES[3].ego_speed_mps
        second_gain_m = (PHASES[5].ego_speed_mps-PHASES[5].lead_speed_mps) * (PHASES[5].end_m-PHASES[5].start_m)/PHASES[5].ego_speed_mps
        self.assertGreater(-15 + first_gain_m, 5)
        self.assertLess(-15 + first_gain_m - reclaim_gain_m, -5)
        self.assertGreater(-15 + first_gain_m - reclaim_gain_m + second_gain_m, 5)
        for previous, current, gap, edge in (
            ('approach', 'first_right_pass_request', -12, -1),
            ('first_right_pass_request', 'first_reentry', 12, 2),
            ('first_reentry', 'lead_reclaim_request', 10, -1),
            ('lead_reclaim_request', 'second_reentry', -12, 2),
            ('second_reentry', 'second_right_pass_request', -12, -1),
        ):
            self.assertTrue(transition_guard(previous, current, gap, edge))
        for previous, current, gap, edge in (
            ('approach', 'first_right_pass_request', 2, -1),
            ('first_right_pass_request', 'first_reentry', -2, 2),
            ('first_reentry', 'lead_reclaim_request', 10, 2),
            ('lead_reclaim_request', 'second_reentry', 8, 2),
            ('second_reentry', 'second_right_pass_request', -12, 2),
        ):
            with self.assertRaises(ValueError):
                transition_guard(previous, current, gap, edge)

    def test_event_envelope_below_at_and_above_one_mile(self):
        for distance, expected in ((MILE_M - .01, True), (MILE_M, True),
                                   (MILE_M + .01, False)):
            result = measure_sequence(sample(distance), episodes(), [0], [6])
            self.assertEqual(result["within_one_mile_envelope"], expected)
            self.assertTrue(result["two_distinct_right_passing_episodes_measured"])
            self.assertFalse(result["offense_decided"])

    def test_rejects_discontinuous_or_unsupported_events(self):
        rows = sample(100)
        rows[3]["frame"] = 8
        with self.assertRaisesRegex(ValueError, "discontinuous"):
            measure_sequence(rows, episodes(), [0], [6])
        with self.assertRaisesRegex(ValueError, "Off-pavement"):
            measure_sequence(sample(100), [dict(episodes()[0], off_pavement_frames=[])], [0], [6])
        overlapping = episodes()
        overlapping[1]["start_frame"] = 2
        with self.assertRaisesRegex(ValueError, "overlap"):
            measure_sequence(sample(100), overlapping, [0], [6])
        wrong_target = episodes()
        wrong_target[1]["target_vehicle_id"] = 10
        with self.assertRaisesRegex(ValueError, "Fixed overtaken vehicle"):
            measure_sequence(sample(100), wrong_target, [0], [6])
        with self.assertRaisesRegex(ValueError, "Off-pavement source frames"):
            measure_sequence(sample(100), [dict(episodes()[0], off_pavement_frames=[999])], [0], [6])


if __name__ == "__main__":
    unittest.main()
