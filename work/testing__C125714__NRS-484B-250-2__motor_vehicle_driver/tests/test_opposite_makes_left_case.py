import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('left_turn', ROOT / 'prove_opposite_left_turn_comparison.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class OppositeMakesLeftTest(unittest.TestCase):
    def test_preturn_fixed_and_turn_observed(self):
        receipt = comparison.audit()
        self.assertEqual(receipt['fixed_approach_frames'], 31)
        self.assertEqual(len(receipt['changed_turn_frames']), 29)
        self.assertEqual(receipt['legal_applicability'], 'unresolved')

    def test_rejects_changed_preturn_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            attempt = Path(folder)
            names = list(comparison.audit()['fixed_sources']) + [
                'crossing_history.jsonl', 'capture/evidence.jsonl',
                'compatibility.json', 'analysis-report.json']
            for name in names:
                dst = attempt / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.TURN / name, dst)
            history = [json.loads(row) for row in (attempt / 'crossing_history.jsonl').read_text().splitlines()]
            history[15]['other']['position_xy_m'] = [5, 3.5]
            (attempt / 'crossing_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in history))
            with self.assertRaisesRegex(ValueError, 'approach changed'):
                comparison.audit(turn=attempt)


if __name__ == '__main__':
    unittest.main()
