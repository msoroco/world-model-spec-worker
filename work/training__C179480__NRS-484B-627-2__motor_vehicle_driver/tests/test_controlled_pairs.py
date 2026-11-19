"""The independent comparison audit rejects missing contrast and changed controls."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'audit_controlled_pairs.py'
spec = importlib.util.spec_from_file_location('controlled_pairs', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ControlledPairAuditTests(unittest.TestCase):
    def test_current_source_pairs(self):
        self.assertTrue(audit.audit().is_file())

    def test_missing_roadway_contrast_rejected(self):
        original = audit.channel

        def changed(name, choice, key):
            rows, digest = original(name, choice, key)
            if name == 'contrast' and choice == 'primary' and key == 'ego_lane_footprint':
                rows[250] = dict(rows[250], driving_lane_overlap=True)
            return rows, digest

        with patch.object(audit, 'channel', changed):
            with self.assertRaisesRegex(ValueError, 'roadway placement contrast absent'):
                audit.audit()

    def test_changed_following_actor_rejected(self):
        original = audit.channel

        def changed(name, choice, key):
            rows, digest = original(name, choice, key)
            if name == 'safe_operation_stop' and choice == 'primary' and key == 'following_actor_gap_history':
                rows[250] = dict(rows[250], gap_m=999)
            return rows, digest

        with patch.object(audit, 'channel', changed):
            with self.assertRaisesRegex(ValueError, 'fixed following_actor_gap_history changed'):
                audit.audit()


if __name__ == '__main__':
    unittest.main()
