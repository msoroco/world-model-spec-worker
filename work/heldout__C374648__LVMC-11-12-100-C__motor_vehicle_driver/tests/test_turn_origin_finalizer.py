import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_origin_finalizer import CASE, analyze, build_result


def sources(root):
    config = {'law_id': 'LVMC-11-12-100-C', 'cell_id': 'C374648',
              'actor': 'motor_vehicle_driver', 'selected_case_id': CASE,
              'case': {'recording_description': {'subject': 'turn origin'}}}
    (root/'config.json').write_text(json.dumps(config))
    (root/'case_context.json').write_text(json.dumps({
        'ego_actor_id': 31, 'target_start_frame': 100,
        'requested_maneuver': 'left turn', 'designation_authority_verified': False}))
    native, frames, trace = [], [], []
    for index, heading in enumerate(([1, 0], [1, 0], [.94, -.34],
                                     [.5, -.866], [0, -1])):
        frame, time = 100+index, index*.05
        native.append({'frame': frame, 'time_s': time, 'ego_id': '31',
                       'ego_forward_xy': heading, 'is_junction': 2 <= index < 4,
                       'road_id': 17 if index < 4 else 25, 'lane_id': 1,
                       'center_turn_road_id': 17, 'center_turn_lane_id': 1,
                       'designation_source': 'authored candidate; authority undecided',
                       'center_marking_source_ids': ['road:17:lane:1:left:Solid',
                                                     'road:17:lane:1:right:Broken']})
        frames.append({'video_frame': index, 'carla_frame': frame, 'time_s': time})
        trace.append({'frame': frame, 'time_s': time})
    for name, rows in (('turn_origin_native.jsonl', native),
                       ('video_frames.jsonl', frames), ('trace.jsonl', trace)):
        (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))


class TurnOriginFinalizerTests(unittest.TestCase):
    def test_saved_source_derives_channel_and_keeps_acceptance_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            report = analyze(root)
            result = build_result(root, report)
            self.assertTrue((root/'turn_origin_observation.jsonl').is_file())
            self.assertTrue(result['realized_observables']['origin_matches_center_lane']['value'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertFalse(result['legal_acceptance_claimed'])

    def test_missing_and_stale_original_sources_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            (root/'turn_origin_native.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            frames = [json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
            frames[2]['carla_frame'] = 900
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
            with self.assertRaisesRegex(ValueError, 'identity join'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
