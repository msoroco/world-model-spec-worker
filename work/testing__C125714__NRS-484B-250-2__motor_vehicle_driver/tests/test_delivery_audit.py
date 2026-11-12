import os
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent.parent
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_audit import audit  # noqa: E402

CASE = PACKAGE.name + '__source_verified_other_right_near_time'
ATTEMPT = REPO / '.runtime-work/c125714-right-near-compat-v10'


class DeliveryAuditTests(unittest.TestCase):
    def test_source_bound_diagnostic_audit(self):
        proof = audit(CASE, ATTEMPT, PACKAGE, diagnostic=True)
        self.assertTrue(proof['software_audit_passed'])
        self.assertEqual(set(proof['camera_decodes']),
                         {'overview', 'approach', 'reference_corner', 'driver_reference'})
        self.assertFalse(proof['physical_acceptance_claimed'])

    def test_missing_original_geometry_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory)
            for source in ATTEMPT.iterdir():
                if source.name != 'road_geometry.json':
                    os.symlink(source.resolve(), copy / source.name, target_is_directory=source.is_dir())
            with self.assertRaisesRegex(ValueError, 'Missing or changed source: road_geometry.json'):
                audit(CASE, copy, PACKAGE, diagnostic=True)

    def test_fixture_cannot_pass_native_acceptance_audit(self):
        with self.assertRaisesRegex(ValueError, 'Native provenance'):
            audit(CASE, ATTEMPT, PACKAGE)


if __name__ == '__main__':
    unittest.main()
