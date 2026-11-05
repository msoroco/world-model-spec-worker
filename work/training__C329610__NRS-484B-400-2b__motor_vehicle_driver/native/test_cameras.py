import unittest
from cameras import PROFILE, RATE_HZ, camera_plan


class CameraPolicyTest(unittest.TestCase):
    def test_profile_and_fallback_frustration_knob(self):
        self.assertEqual(PROFILE,"overview1080-capability-v1")
        self.assertEqual(RATE_HZ,20)
        primary=camera_plan("primary")
        alternate=camera_plan("fallback3")
        self.assertEqual([(v["name"],v["width"],v["height"]) for v in primary],
                         [("overview",1920,1080),("approach",1280,720),
                          ("reference_corner",1280,720),("driver_reference",1280,720)])
        self.assertEqual([v["name"] for v in primary],[v["name"] for v in alternate])
        self.assertEqual(primary[0],alternate[0])
        self.assertEqual(primary[2:],alternate[2:])
        self.assertNotEqual(primary[1]["fov_deg"],alternate[1]["fov_deg"])
        self.assertNotEqual(primary[1]["xyz_m"],alternate[1]["xyz_m"])
        self.assertEqual(camera_plan("fallback1"),primary)
        self.assertEqual(camera_plan("fallback2"),primary)


if __name__ == "__main__":
    unittest.main()
