import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from arrival_timing_audit import audit


class ArrivalTimingAuditTests(unittest.TestCase):
    def test_source_bound_contrast_and_changed_topology_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            roots = [Path(temporary) / name for name in ('near', 'separated')]
            for root, filename in zip(roots, ('diagnostic-ending-yields.json',
                                             'diagnostic-separated-arrival.json')):
                root.mkdir()
                files = json.loads((ROOT / filename).read_text())['files']
                for name in ('intersection_topology.json', 'intersection_participants.jsonl'):
                    (root / name).write_text(files[name])
            proof = audit(*roots)
            self.assertGreater(proof['separated_entry_delta_s'], proof['near_entry_delta_s'])
            self.assertIsNone(proof['legal_approximately_same_time_judgment'])
            topology = json.loads((roots[1] / 'intersection_topology.json').read_text())
            topology['lanes']['o2']['highway_id'] = 'changed'
            (roots[1] / 'intersection_topology.json').write_text(json.dumps(topology))
            with self.assertRaisesRegex(ValueError, 'changed fixed lane topology'):
                audit(*roots)


if __name__ == '__main__':
    unittest.main()
