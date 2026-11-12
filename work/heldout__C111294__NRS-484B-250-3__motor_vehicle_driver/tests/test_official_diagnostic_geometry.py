import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from official_diagnostic_geometry import rebuild
from official_geometry_source_audit import audit


class OfficialDiagnosticGeometryTests(unittest.TestCase):
    def test_red_and_green_diagnostics_join_their_original_map(self):
        bindings = []
        for label in ('device', 'green'):
            with self.subTest(label=label), TemporaryDirectory() as temp:
                raw = json.loads((ROOT / f'diagnostic-official-{label}.json').read_text())
                diagnostic = rebuild(raw)
                for name in ('road.xodr', 'intersection_topology.json',
                             'official_device_context.json', 'official_geometry_binding.json'):
                    (Path(temp) / name).write_text(diagnostic['files'][name])
                receipt = audit(temp)
                self.assertEqual(receipt['signal_id'], 'signal-8')
                self.assertFalse(receipt['physical_realization_claimed'])
                bindings.append(receipt['geometry_sha256'])
        self.assertEqual(bindings[0], bindings[1])


if __name__ == '__main__':
    unittest.main()
