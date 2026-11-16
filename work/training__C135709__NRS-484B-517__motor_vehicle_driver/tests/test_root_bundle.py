"""Portable CPU checks for the selected root bundle and delivery audit."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline'))
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from scenario_pipeline.worker_exchange.execution_manifest import validate
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange import media


def load_auditor():
    spec = importlib.util.spec_from_file_location('c135709_delivery_audit',
                                                  ROOT/'native/delivery_audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RootBundleTests(unittest.TestCase):
    def test_exact_root_runner_check(self):
        subprocess.run([sys.executable, str(ROOT/'runner.py'), '--check'],
                       cwd=REPO, check=True, capture_output=True, text=True)

    def test_both_manifest_cases_and_delivery_proofs(self):
        manifest = validate(REPO, ROOT.name)
        self.assertEqual(len(manifest['cases']), 2)
        for entry in manifest['cases']:
            validate_case(ROOT, entry, {'full-train'})

    def test_reviewed_pixels_reject_flat_content(self):
        audit = load_auditor()
        boxes = [{'claim': claim, 'frame': 0, 'rect_xywh': [0, 0, 3, 3]}
                 for claim in sorted(audit.CLAIMS)]
        check, seen = audit.pixel_checker(boxes)
        check(media.Frame(0, 3, 3, bytes(range(27))))
        self.assertEqual(seen, audit.CLAIMS)
        with self.assertRaisesRegex(ValueError, 'flat'):
            check(media.Frame(0, 3, 3, bytes([0]*27)))


if __name__ == '__main__':
    unittest.main()
