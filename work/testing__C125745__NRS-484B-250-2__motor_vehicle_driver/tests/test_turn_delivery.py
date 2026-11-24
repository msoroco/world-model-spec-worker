"""Independent CPU comparison audit rejection checks."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audit_turn_delivery import audit

HERE = Path(__file__).resolve().parents[1]
FILES = ('fourth-site.json', 'fourth-construction.json',
         'stop_opposite_left_turn-primary-current-runtime-compatibility.json',
         'stop_opposite_left_turn-primary-current-runtime-analysis.log',
         'stop_opposite_left_turn-primary-current-runtime-negative.log',
         'fourth-primary-saved-v1.log',
         'straight-site.json', 'straight-construction.json',
         'stop_opposite_straight-primary-compatibility.json',
         'stop_opposite_straight-primary-analysis.log',
         'stop_opposite_straight-primary-negative.log',
         'stop_opposite_straight-primary-saved.json')


class TurnDeliveryAuditTests(unittest.TestCase):
    def test_positive_and_changed_source_rejection(self):
        report = audit(HERE)
        self.assertTrue(report['recorded_only_passed'])
        self.assertFalse(report['physical_acceptance_claimed'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / HERE.name
            root.mkdir()
            for name in FILES:
                shutil.copyfile(HERE / name, root / name)
            self.assertEqual(audit(root)['comparison']['straight_exit_offset_m'], 0)
            path = root / 'straight-site.json'
            scene = json.loads(path.read_text())
            scene['approaches']['other']['route_xy_m'][-1] = [15, 15]
            path.write_text(json.dumps(scene) + '\n')
            with self.assertRaisesRegex(ValueError, 'source binding'):
                audit(root)

    def test_saved_source_claim_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / HERE.name
            root.mkdir()
            for name in FILES:
                shutil.copyfile(HERE / name, root / name)
            path = root / 'stop_opposite_straight-primary-saved.json'
            saved = json.loads(path.read_text())
            saved['physical_acceptance_claimed'] = True
            path.write_text(json.dumps(saved) + '\n')
            with self.assertRaisesRegex(ValueError, 'saved-source'):
                audit(root)


if __name__ == '__main__':
    unittest.main()
