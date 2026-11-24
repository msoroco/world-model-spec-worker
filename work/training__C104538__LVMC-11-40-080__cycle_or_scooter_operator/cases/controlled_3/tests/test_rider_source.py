import json
import unittest
from pathlib import Path
import runner
class RiderSource(unittest.TestCase):
    def test_unreviewed_original_row(self):
        sign=json.loads(Path('authored-sign-source.json').read_text())
        sample={'native_center_xy_m':[1.25,4.0],'time_s':.05}
        row=runner.rider_observation_row(1,sample,sign,107)
        self.assertEqual((row['actor_id'],row['sign_id']),('107',sign['id']))
        self.assertIsNone(row['mounted'])
        self.assertIsNone(row['walking_machine'])
        self.assertIsNone(row['u_turn_active'])
        self.assertEqual(row['posture_source'],'original_pixel_review_pending')
