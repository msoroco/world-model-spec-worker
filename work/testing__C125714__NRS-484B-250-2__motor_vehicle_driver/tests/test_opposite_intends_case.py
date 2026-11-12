import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison', ROOT / 'prove_opposite_intention_comparison.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class OppositeIntendsLeftTest(unittest.TestCase):
    def test_isolated_intention(self):
        receipt = comparison.audit()
        self.assertEqual(receipt['legal_applicability'], 'unresolved')
        self.assertEqual(len(receipt['fixed_sources']), 10)
        self.assertEqual([r['intention'] for r in receipt['results']], ['straight', 'left'])

    def test_rejects_changed_fixed_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder)
            for name in comparison.audit()['fixed_sources']:
                destination = replacement / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.LEFT_ATTEMPT / name, destination)
            for name in ('turn_intent.json', 'compatibility.json', 'analysis-report.json'):
                shutil.copyfile(comparison.LEFT_ATTEMPT / name, replacement / name)
            (replacement / 'road_geometry.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Fixed source differs'):
                comparison.audit(left=replacement)

    def test_rejects_unisolated_intention(self):
        with tempfile.TemporaryDirectory() as folder:
            replacement = Path(folder)
            for name in comparison.audit()['fixed_sources']:
                destination = replacement / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.LEFT_ATTEMPT / name, destination)
            for name in ('turn_intent.json', 'compatibility.json', 'analysis-report.json'):
                shutil.copyfile(comparison.LEFT_ATTEMPT / name, replacement / name)
            intent = json.loads((replacement / 'turn_intent.json').read_text())
            intent['intended_maneuver'] = 'straight'
            (replacement / 'turn_intent.json').write_text(json.dumps(intent))
            with self.assertRaisesRegex(ValueError, 'Intention difference'):
                comparison.audit(left=replacement)


if __name__ == '__main__':
    unittest.main()
