import json
import unittest
from runner import config_check, request

class TestSignedRoad(unittest.TestCase):
    def test_exact_route(self):
        cfg = config_check()
        self.assertEqual(cfg['case_id'], 'training__C230207__LVMC-11-40-180-B__cycle_or_scooter_operator__witness_2')
        self.assertFalse(request(200, cfg)['observed_motion'])
