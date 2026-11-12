import json
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from lamp_comparison_audit import audit
from test_lamp_finalizer import fixture


class TestLampComparisonAudit(unittest.TestCase):
    def test_both_comparisons_and_changed_fixed_condition(self):
        pairs = [('optional_equipment', 'no_backup_lamp_installed',
                  'forward_backup_lamp_off'),
                 ('forward_illumination', 'forward_backup_lamp_off',
                  'forward_backup_lamp_on')]
        for comparison, a, b in pairs:
            with self.subTest(comparison=comparison), tempfile.TemporaryDirectory() as x, tempfile.TemporaryDirectory() as y:
                first, second = Path(x), Path(y)
                fixture(first, a); fixture(second, b)
                receipt = audit(comparison, first, second)
                self.assertTrue(receipt['fixed_conditions_checked'])
                self.assertFalse(receipt['actual_pixels_reviewed'])
                config = json.loads((second/'config.json').read_text())
                config['approach_m'] = 50
                (second/'config.json').write_text(json.dumps(config))
                with self.assertRaisesRegex(ValueError, 'Fixed construction condition'):
                    audit(comparison, first, second)

    def test_rejects_changed_context_and_missing_deliberate_difference(self):
        with tempfile.TemporaryDirectory() as x, tempfile.TemporaryDirectory() as y:
            first, second = Path(x), Path(y)
            fixture(first, 'forward_backup_lamp_off')
            fixture(second, 'forward_backup_lamp_on')
            context = json.loads((second/'intersection_context.json').read_text())
            context['junction_id'] = 99
            (second/'intersection_context.json').write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'Fixed intersection'):
                audit('forward_illumination', first, second)
            context['junction_id'] = 42
            (second/'intersection_context.json').write_text(json.dumps(context))
            rows = [json.loads(line) for line in (second/'motion.jsonl').read_text().splitlines()]
            for row in rows: row['native_backup_lamp_bit'] = False
            (second/'motion.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'lamp-on readback'):
                audit('forward_illumination', first, second)


if __name__ == '__main__': unittest.main()
