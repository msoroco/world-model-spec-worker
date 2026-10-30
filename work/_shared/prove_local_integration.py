"""Synthetic local delivery integration proof; no CARLA or campaign state."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'runtime/main-pipeline-v6'
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME/'scenario_pipeline'))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class RepeatImportTest(unittest.TestCase):
    def test_repeat_import_uses_local_checkout_without_git(self):
        from worker_exchange import exchange
        from worker_exchange.common import tree, write
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root/'local-checkout'
            write(repo/'batch.json', {'batch_id':'fixture'})
            receipt = {'package_sha256':'fixture-package','local_checkout':str(repo)}
            write(root/'inputs/worker_exchange/fixture/import-fixture-package.json', receipt)
            with (patch('worker_exchange.exchange.check_return',return_value={
                    'package_sha256':'fixture-package','files':tree(repo)}),
                  patch('worker_exchange.exchange._git_identity',
                        side_effect=AssertionError('Git must not be used for local checkout'))):
                self.assertEqual(exchange.import_return(root,repo,'fixture'),receipt)


def main():
    handoff = module(RUNTIME/'tests/test_worker_delivery_handoff.py','handoff_fixture')
    candidates = module(RUNTIME/'tests/test_worker_candidates.py','candidate_fixture')
    suite = unittest.TestSuite([
        handoff.DeliveryHandoffTests('test_local_model_free_semantic_adoption'),
        handoff.DeliveryHandoffTests('test_exact_dispatch_cannot_run_other_jobs'),
        handoff.DeliveryHandoffTests('test_local_acceptance_references_one_recording_in_both_sets'),
        candidates.CandidateTests('test_saved_processing_rejects_mismatched_selection_before_conversion'),
        RepeatImportTest('test_repeat_import_uses_local_checkout_without_git'),
    ])
    result = unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit(1)
    saved = subprocess.run([sys.executable, str(ROOT/'work/_shared/prove_saved_processing_v6.py')],
                           cwd=ROOT, capture_output=True, text=True)
    print(saved.stdout[-1200:])
    if saved.returncode:
        print(saved.stderr[-1200:])
        raise SystemExit(saved.returncode)
    print(json.dumps({
        'scenarios':['primary_job','fallback_job','saved_processing','rejected_audit','accepted_both_sets','repeat_import_local_checkout'],
        'accepted_recording_id':'a'*64,
        'test_selections':{'demo-test':'a'*64,'full-test':'a'*64},
        'failed_audit_memberships':{'demo-test':0,'full-test':0},
        'scope':'synthetic local software integration only'
    },indent=2))

if __name__=='__main__':main()
