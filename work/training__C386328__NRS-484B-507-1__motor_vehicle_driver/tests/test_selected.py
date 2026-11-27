import unittest

from freight_scene import CASES, CAMERAS, scene_request, validate_request
from runner import check


class SelectedFreightSceneTest(unittest.TestCase):
    def test_all_exact_source_requests(self):
        for slug in CASES:
            scene = scene_request(slug)
            self.assertEqual(validate_request(scene)['planned_frames'], 600)
            self.assertEqual({item['name'] for item in scene['cameras']}, CAMERAS)
            self.assertFalse(scene['sign']['actual_text_and_hours_verified'])

    def test_material_signed_hours_and_passenger_wait_contrasts(self):
        scenes = {key: scene_request(key) for key in CASES}
        self.assertNotEqual(scenes['probe_1']['material']['requested_activity'],
                            scenes['probe_2']['material']['requested_activity'])
        self.assertNotEqual(scenes['probe_2']['civil_time']['requested_minute_local'],
                            scenes['probe_3']['civil_time']['requested_minute_local'])
        self.assertNotEqual(scenes['probe_2']['passenger']['requested_activity'],
                            scenes['probe_4']['passenger']['requested_activity'])
        self.assertNotEqual(scenes['probe_4']['material_transport_vehicle']['requested_waiting_to_enter'],
                            scenes['probe_5']['material_transport_vehicle']['requested_waiting_to_enter'])
        for scene in scenes.values():
            self.assertEqual(scene['road_opendrive'], scenes['probe_1']['road_opendrive'])

    def test_runner_check_is_cpu_only(self):
        report = check()
        self.assertEqual(len(report['case_ids']), 5)
        self.assertFalse(report['original_native_observed'])


if __name__ == '__main__':
    unittest.main()
