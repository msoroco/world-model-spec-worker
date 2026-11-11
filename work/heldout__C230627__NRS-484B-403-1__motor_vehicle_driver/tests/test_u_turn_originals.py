import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_originals import UTurnSourceRecorder
from u_turn_measurement import measure
from u_turn_finalizer import analyze


class Actor:
    def __init__(self, identity, x, y, yaw=0):
        self.id, self.x, self.y, self.yaw = identity, x, y, yaw
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2, y=1))

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=self.yaw))

    def get_velocity(self):
        return SimpleNamespace(x=2, y=0)


class OriginalTests(unittest.TestCase):
    def test_original_join_and_no_legal_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            ego, oncoming, following = Actor(1, 0, 0), Actor(2, 20, 3.5), Actor(3, -15, 0)
            scene = {'road_id': 7, 'approach_lane_id': -1, 'opposite_lane_id': 1}
            recorder = UTurnSourceRecorder(directory, ego,
                                           {'oncoming': oncoming, 'following': following}, scene)
            for index, yaw in enumerate((0, 10, 90, 179)):
                ego.x = index * 2
                ego.yaw = yaw
                recorder.append(100 + index, index * .05)
            recorder.close()
            observation = measure(Path(directory)/'u_turn_motion.jsonl',
                                  Path(directory)/'u_turn_context.json')
            self.assertEqual(observation['turn_onset_frame'], 101)
            self.assertEqual(observation['last_observed_frame'], 103)
            self.assertIsNone(observation['safe_turn_legal_judgment'])
            self.assertTrue(all(x['value'] is None for x in
                                observation['prohibition_context'].values()))
            self.assertEqual(set(observation['participant_roles']), {'2', '3'})

    def test_discontinuity_and_identity_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ego = Actor(1, 0, 0)
            oncoming, following = Actor(2, 20, 3.5), Actor(3, -15, 0)
            recorder = UTurnSourceRecorder(directory, ego,
                                           {'oncoming': oncoming, 'following': following},
                                           {'road_id': 7, 'approach_lane_id': -1,
                                            'opposite_lane_id': 1})
            recorder.append(100, 0)
            with self.assertRaisesRegex(ValueError, 'discontinuity'):
                recorder.append(102, .1)
            recorder.close()

    def test_saved_join_and_missing_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ego, oncoming, following = Actor(1, 0, 0), Actor(2, 20, 3.5), Actor(3, -15, 0)
            recorder = UTurnSourceRecorder(root, ego,
                                           {'oncoming': oncoming, 'following': following},
                                           {'road_id': 7, 'approach_lane_id': -1,
                                            'opposite_lane_id': 1})
            for index, yaw in enumerate((0, 10, 90, 179)):
                ego.yaw = yaw
                recorder.append(100 + index, index * .05)
            recorder.close()
            (root/'config.json').write_text(json.dumps({
                'selected_case_id': 'heldout__C230627__NRS-484B-403-1__motor_vehicle_driver__safety_clear',
                'law_id': 'NRS-484B-403-1', 'cell_id': 'C230627',
                'actor': 'motor_vehicle_driver'}))
            (root/'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame': i, 'carla_frame': 100+i, 'time_s': i*.05})+'\n'
                for i in range(4)))
            (root/'trace.jsonl').write_text(''.join(json.dumps({
                'frame': 100+i, 'time_s': i*.05})+'\n' for i in range(4)))
            report = analyze(root)
            self.assertEqual(report['measurements']['u_turn_observation']['value']['last_observed_frame'], 103)
            self.assertTrue((root/'u_turn_observation.jsonl').is_file())
            (root/'u_turn_observation.jsonl').unlink()
            (root/'trace.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: trace.jsonl'):
                analyze(root)

    def test_mapped_device_source_retained_without_official_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ego, oncoming, following = Actor(1, 0, 0), Actor(2, 20, 3.5), Actor(3, -15, 0)
            device = {'landmark_id': 'sign-1', 'road_id': 7,
                      'distance_to_approach_m': 12,
                      'source_fields': {'name': 'NO_U_TURN',
                                        'type': 'regulatory', 'value': ''}}
            recorder = UTurnSourceRecorder(root, ego,
                                           {'oncoming': oncoming, 'following': following},
                                           {'road_id': 7, 'approach_lane_id': -1,
                                            'opposite_lane_id': 1}, device=device)
            for index, yaw in enumerate((0, 10, 90, 179)):
                ego.yaw = yaw
                recorder.append(100+index, index*.05)
            recorder.close()
            (root/'config.json').write_text(json.dumps({
                'selected_case_id': 'heldout__C230627__NRS-484B-403-1__motor_vehicle_driver__prohibition_403_2',
                'law_id': 'NRS-484B-403-1', 'cell_id': 'C230627',
                'actor': 'motor_vehicle_driver'}))
            (root/'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame': i, 'carla_frame': 100+i, 'time_s': i*.05})+'\n'
                for i in range(4)))
            (root/'trace.jsonl').write_text(''.join(json.dumps({
                'frame': 100+i, 'time_s': i*.05})+'\n' for i in range(4)))
            report = analyze(root)
            observed = report['measurements']['mapped_no_u_turn_device']['value']
            self.assertEqual(observed['landmark_id'], 'sign-1')
            self.assertIsNone(observed['official_device_status'])
            (root/'u_turn_observation.jsonl').unlink()
            source = json.loads((root/'u_turn_device.json').read_text())
            source['mapped_no_u_turn_device']['official_device_status'] = True
            (root/'u_turn_device.json').write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, 'cannot claim official'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
