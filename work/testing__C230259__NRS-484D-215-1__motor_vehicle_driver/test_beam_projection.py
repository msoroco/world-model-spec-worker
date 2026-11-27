import unittest

from beam_projection import bbox, eye_cube, project


IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


class ProjectionTests(unittest.TestCase):
    def test_forward_center_and_rightward_pixel(self):
        self.assertEqual(project([100, 0, 0], IDENTITY, 1280, 720, 90), [640, 360])
        self.assertGreater(project([100, 10, 0], IDENTITY, 1280, 720, 90)[0], 640)

    def test_original_eye_cube_has_eight_corners_and_projected_roi(self):
        cube = eye_cube([152.4, 0, 1.4], .18)
        self.assertEqual(len(cube), 8)
        roi = bbox(cube, IDENTITY, 1280, 720, 20, margin_px=2)
        self.assertGreater(roi[2] - roi[0], 3)
        self.assertGreater(roi[3] - roi[1], 3)

    def test_behind_camera_rejected(self):
        with self.assertRaisesRegex(ValueError, "behind"):
            project([-1, 0, 0], IDENTITY, 1280, 720, 20)

    def test_invalid_calibration_rejected(self):
        with self.assertRaisesRegex(ValueError, "calibration"):
            project([1, 0, 0], IDENTITY, 1280, 720, 180)


if __name__ == "__main__":
    unittest.main()
