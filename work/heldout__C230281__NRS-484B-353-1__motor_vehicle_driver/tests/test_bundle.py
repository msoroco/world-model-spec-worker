import json
import unittest
from pathlib import Path
from school_bus_native import CASE_ID, check_plan, check_scene
from school_bus_camera import CAMERAS

class Bundle(unittest.TestCase):
    def test_exact_first_case_scene_and_four_views(self):
        root=Path(__file__).resolve().parents[1]
        plan=json.loads((root/'case-plan.json').read_text())
        config=json.loads((root/'config.json').read_text())
        self.assertTrue(check_plan(plan, CASE_ID))
        self.assertIs(check_scene(config),config)
        self.assertEqual([x['name'] for x in config['cameras']],list(CAMERAS))
        self.assertEqual(config['frames'],160)
        self.assertEqual(config['school_bus_lamp_review']['roi_status'].split()[0],'unreviewed')

if __name__ == '__main__':unittest.main()
