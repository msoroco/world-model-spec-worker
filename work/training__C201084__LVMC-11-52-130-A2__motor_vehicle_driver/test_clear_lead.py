"""CPU checks for the lead-position boundary probe."""
import json
import tempfile
import unittest
from pathlib import Path

from conflict_controller import decision
from exception_runner import run
from test_exception_probe import environment

HERE = Path(__file__).resolve().parent


class ClearLeadTests(unittest.TestCase):
    def test_near_and_far_lead_request_follows_observed_speed(self):
        def request(lead_x, speed):
            return decision((10, 1), (speed, 0), (lead_x, 1), (0, 0), 0)
        self.assertTrue(request(18, 4)['brake_requested_from_lead_relation'])
        self.assertFalse(request(18, 2)['brake_requested_from_lead_relation'])
        self.assertFalse(request(18, 0)['brake_requested_from_lead_relation'])
        for speed in (4, 2, 0):
            self.assertFalse(request(35, speed)['brake_requested_from_lead_relation'])

    def test_clear_lead_survey_reaches_native_capture(self):
        client, carla, spawned = environment()
        survey = json.loads((HERE/'draft-clear-survey.json').read_text())
        survey['map_name'] = 'TownFireLane'
        with tempfile.TemporaryDirectory() as tmp:
            def capture(world, carla, ego, follower, lead, sign, plan, attempt):
                self.assertEqual(plan['conflict_probe']['lead_spawn_xy_m'], [35, 1])
                self.assertEqual(plan['capture_frames'], 600)
                self.assertEqual(len(plan['camera_names']), 4)
                return {'source_frames': 600}
            result = run(client, carla, survey, Path(tmp)/'attempt',
                         acquisition=capture, processor=lambda _: {
                             'physical_or_legal_completion_claimed': False,
                             'statutory_necessity_verified': False})
            self.assertFalse(result['physical_or_legal_completion_claimed'])
            self.assertEqual(result['lead_actor_id'], 102)
        self.assertEqual(spawned[-3:], ['destroy']*3)


if __name__ == '__main__':
    unittest.main()
