"""Independent electric acceptance gate tests using synthetic review metadata."""
import unittest

from electric_delivery_audit import ASSIGNMENT, case_identity, review_original


class ElectricDeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.binding = {'native_actor_id': 42,
                        'review_source_sha256': {'asset.txt': 'a' * 64}}
        self.sources = {'trace.jsonl': 'b' * 64}
        self.videos = {'overview.mkv': 'c' * 64}
        self.review = {
            'original_pixel_reviewed': True,
            'named_geography_verified': True,
            'sign_face_three_class_text_verified': True,
            'sidewalk_occupancy_reviewed': True,
            'operator_posture_reviewed': True,
            'electric_class_independently_verified': 'electric_scooter',
            'electric_power_source_reviewed': True,
            'electric_device_geometry_reviewed': True,
            'native_actor_id': 42,
            'electric_asset_source_sha256': self.binding['review_source_sha256'],
            'observed_behavior': 'mounted_sidewalk',
            'source_sha256': self.sources,
            'video_sha256': self.videos,
        }

    def test_exact_case_and_complete_review_shape(self):
        self.assertEqual(case_identity(ASSIGNMENT + '__electric_scooter_mounted_sidewalk'),
                         ('electric_scooter', 'mounted_sidewalk'))
        self.assertIsNone(review_original(self.review, 'electric_scooter',
                                          'mounted_sidewalk', self.binding,
                                          self.sources, self.videos))
        with self.assertRaisesRegex(ValueError, 'Wrong exact'):
            case_identity(ASSIGNMENT + '__electric_scooter_wrong')

    def test_missing_original_class_or_power_review_rejected(self):
        for key, value in (('electric_class_independently_verified', 'electric_bicycle'),
                           ('electric_power_source_reviewed', False),
                           ('native_actor_id', 43),
                           ('electric_asset_source_sha256', {})):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'class, power, geometry or actor'):
                    review_original({**self.review, key: value}, 'electric_scooter',
                                    'mounted_sidewalk', self.binding,
                                    self.sources, self.videos)

    def test_changed_pixels_and_behavior_rejected(self):
        with self.assertRaisesRegex(ValueError, 'pixels changed'):
            review_original({**self.review, 'video_sha256': {}}, 'electric_scooter',
                            'mounted_sidewalk', self.binding,
                            self.sources, self.videos)
        with self.assertRaisesRegex(ValueError, 'behavior differs'):
            review_original({**self.review, 'observed_behavior': 'walk_cycle'},
                            'electric_scooter', 'mounted_sidewalk', self.binding,
                            self.sources, self.videos)
