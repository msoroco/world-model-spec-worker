import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture import check_capture

class TestRightExitSource(unittest.TestCase):
    def test_source_and_camera_profile(self):
        value=check_capture(Path(__file__).resolve().parents[1])
        self.assertEqual(value['camera_names'],
            ['overview','approach','reference_corner','driver_reference'])
        self.assertEqual(value['requested_phases'],['circulation','entry','exit'])
        self.assertFalse(value['original_native_observed'])
