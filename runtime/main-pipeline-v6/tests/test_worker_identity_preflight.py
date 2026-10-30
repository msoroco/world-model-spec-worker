import unittest
from scenario_pipeline.worker_exchange.identity_preflight import validate


class IdentityPreflightTests(unittest.TestCase):
    def construction(self, role='subject_127_1', header='C101303 road'):
        return {'files': [
            {'path': 'runner.py', 'content': "blueprint.set_attribute('role_name', %r)\n" % role},
            {'path': 'scene.xodr', 'content': '<OpenDRIVE><header name=%r /></OpenDRIVE>' % header},
        ]}

    def test_matching_labels_pass(self):
        self.assertTrue(validate(self.construction(), 'NRS-484B-127-1', 'C101303')['identity_labels_checked'])

    def test_copied_law_label_fails(self):
        with self.assertRaisesRegex(ValueError, 'another law'):
            validate(self.construction(role='subject_speed_600_1e'), 'NRS-484B-127-1', 'C101303')

    def test_reused_geometry_source_label_is_allowed(self):
        self.assertTrue(validate(self.construction(header='C104496 straight physical crest'),
                                 'NRS-484B-127-1', 'C101303')['identity_labels_checked'])

    def test_law_without_subsection_is_supported(self):
        self.assertTrue(validate(self.construction(role='subject'), 'NRS-484B-407', 'C101303')['identity_labels_checked'])

    def test_synthetic_law_fixture_does_not_require_nrs_suffix(self):
        self.assertFalse(validate(self.construction(role='subject'), 'LAW-1', 'C1')['identity_labels_checked'])


if __name__ == '__main__':
    unittest.main()
