"""Assignment-local CPU checks for the portable exact-case handoff."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SelectedHandoff(unittest.TestCase):
    def test_canonical_root_source_request(self):
        run = subprocess.run([sys.executable, str(BASE / 'runner.py'), '--check'],
                             check=True, capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['original_native_observed'])

    def test_six_source_bound_cpu_chains(self):
        manifest_path = BASE / 'selected-v5-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        index = json.loads((BASE / 'selected-v5/cpu-proof-index.json').read_text())
        self.assertEqual(index['manifest_sha256'], sha(manifest_path))
        self.assertEqual(len(manifest['cases']), 2)
        for entry in manifest['cases']:
            suffix = entry['case_id'].rsplit('__', 1)[1]
            for candidate, selected in [('primary', entry),
                                        *[(x['id'], x) for x in entry['candidates']]]:
                self.assertEqual(selected['construction_sha256'],
                                 sha(BASE / selected['construction']))
                proof = BASE / 'selected-v5' / suffix / candidate / 'proofs'
                receipt = json.loads((proof / 'compatibility.json').read_text())
                saved = json.loads((proof / 'saved-processing.json').read_text())
                self.assertTrue(receipt['passed'])
                self.assertEqual(receipt['construction_sha256'],
                                 selected['construction_sha256'])
                self.assertEqual(receipt['negative_removed'], 'actor-history.json')
                self.assertTrue(saved['passed'] and saved['recorded_only'])
                self.assertTrue(saved['originals_preserved'])
                self.assertFalse(saved['physical_acceptance_claimed'])
                self.assertFalse(saved['legal_acceptance_claimed'])

    def test_physical_and_comparison_diagnostics(self):
        comparison = json.loads((BASE / 'selected-v3/comparison-audit.json').read_text())
        self.assertEqual(set(comparison['candidate_pairs']),
                         {'primary', 'fallback1', 'fallback2'})
        for row in comparison['candidate_pairs'].values():
            self.assertTrue(row['other_actor_body_fixed'])
            self.assertEqual(row['frames'], 600)
        for suffix in ('controlled_1', 'controlled_2'):
            proof = json.loads((BASE / 'selected-v5/physical-proofs' / suffix / 'proof.json').read_text())
            self.assertFalse(proof['original_native_motion_verified'])
            self.assertEqual({x['kind'] for x in proof['fixtures']},
                             {'complete_motion', 'incomplete_motion', 'missing_evidence'})


if __name__ == '__main__':
    unittest.main()
