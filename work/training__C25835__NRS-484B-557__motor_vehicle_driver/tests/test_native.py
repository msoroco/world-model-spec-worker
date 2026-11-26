import json
import unittest
from pathlib import Path

from runner import check
from rail_stop_controller import RailStopController, STOP_CENTER_DISTANCE_FT
from rail_stop_scene import scene_request, validate_request


class NativeRailRequest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_bundle(self):
        result = check(self.config)
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['administrative_designation_verified'])

    def test_all_boundary_requests(self):
        for suffix, feet in STOP_CENTER_DISTANCE_FT.items():
            with self.subTest(suffix=suffix):
                request = scene_request(suffix)
                self.assertEqual(validate_request(request)['camera_count'], 4)
                controller = RailStopController(suffix, 0)
                self.assertAlmostEqual(-controller.target_x * 3.280839895013123, feet)

    def test_no_authored_authority_claim(self):
        request = scene_request(self.config['case_id'].rsplit('__', 1)[-1])
        self.assertFalse(request['stop_sign']['official_governance_verified'])
        self.assertFalse(request['rails']['physical_railroad_status_verified'])


if __name__ == '__main__':
    unittest.main()
