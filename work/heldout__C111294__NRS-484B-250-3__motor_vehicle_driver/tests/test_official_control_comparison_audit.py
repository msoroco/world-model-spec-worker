import json
import sys
import unittest
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from official_control_comparison_audit import audit_sources, audit_attempts


class OfficialControlComparisonTests(unittest.TestCase):
    def sources(self):
        base=json.loads((ROOT/'diagnostic-ending-yields.json').read_text())['files']
        controlled=json.loads((ROOT/'diagnostic-official-device.json').read_text())['files']
        return base,controlled

    def test_fixed_originals_and_governing_device(self):
        base,controlled=self.sources()
        proof=audit_sources(base,controlled)
        self.assertEqual(proof['device_frames'],9)
        self.assertFalse(proof['legal_exception_claimed'])
        changed=dict(controlled)
        rows=[json.loads(line) for line in controlled['official_device_states.jsonl'].splitlines()]
        rows[1]['device_id']='wrong'
        changed['official_device_states.jsonl']=''.join(json.dumps(row)+'\n' for row in rows)
        with self.assertRaisesRegex(ValueError,'state/frame join'):
            audit_sources(base,changed)
        changed=dict(controlled, **{'intersection_participants.jsonl':'{}\n'})
        with self.assertRaisesRegex(ValueError,'changed fixed original'):
            audit_sources(base,changed)
        changed=dict(base)
        changed.pop('control_inventory.json')
        with self.assertRaisesRegex(ValueError,'Missing original comparison source'):
            audit_sources(changed,controlled)

    def test_retained_attempts_and_missing_original(self):
        base, controlled = self.sources()
        with tempfile.TemporaryDirectory() as location:
            roots = [Path(location)/'plain', Path(location)/'governed']
            for root, sources in zip(roots, (base, controlled)):
                root.mkdir()
                for name, value in sources.items():
                    (root/name).parent.mkdir(parents=True, exist_ok=True)
                    (root/name).write_text(value)
            proof = audit_attempts(*roots)
            self.assertEqual(proof['device_frames'], 9)
            self.assertIn('intersection_topology.json', proof['original_source_sha256'][0])
            with self.assertRaisesRegex(ValueError, 'distinct attempts'):
                audit_attempts(roots[0], roots[0])
            (roots[1]/'official_device_states.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original comparison source'):
                audit_attempts(*roots)


if __name__=='__main__':unittest.main()
