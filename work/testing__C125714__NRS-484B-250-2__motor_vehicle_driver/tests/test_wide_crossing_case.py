import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wide_comparison', ROOT / 'prove_wide_crossing_comparison.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class WideCrossingCaseTest(unittest.TestCase):
    def test_gap_measurement_and_fixed_sources(self):
        receipt = comparison.audit()
        self.assertEqual(receipt['roadway_edge_gap_m'], {'near': 1, 'wide': 12})
        self.assertEqual(receipt['statutory_crossing_identity'], 'unresolved')
        self.assertEqual(len(receipt['fixed_sources']), 10)

    def test_rejects_changed_fixed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            attempt = Path(folder)
            names = list(comparison.audit()['fixed_sources']) + [
                'site-sources/median_spacing_source.json', 'median_geometry_source.json',
                'analysis-report.json', 'compatibility.json']
            for name in names:
                dst = attempt / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.WIDE / name, dst)
            (attempt / 'road_geometry.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Fixed crossing source differs'):
                comparison.audit(wide=attempt)

    def test_rejects_unbound_gap_source(self):
        with tempfile.TemporaryDirectory() as folder:
            attempt = Path(folder)
            names = list(comparison.audit()['fixed_sources']) + [
                'site-sources/median_spacing_source.json', 'median_geometry_source.json',
                'analysis-report.json', 'compatibility.json']
            for name in names:
                dst = attempt / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.WIDE / name, dst)
            document = json.loads((attempt / 'median_geometry_source.json').read_text())
            document['source_description'] += ' tampered'
            (attempt / 'median_geometry_source.json').write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, 'not source-bound'):
                comparison.audit(wide=attempt)


if __name__ == '__main__':
    unittest.main()
