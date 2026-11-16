"""Validate every selected release-grid CPU proof and its exact source binding."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.physical_preparation import validate as validate_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(ROOT / 'execution-manifest.json')
    index = read(ROOT / 'hazard-release-draft-proof-index.json')
    entries = [item for item in manifest['cases'] if item['case_id'].endswith(
        ('__approaching_release_3s', '__approaching_release_5s'))]
    assert len(manifest['cases']) == 16 and len(entries) == 2
    evidence = []
    for entry in entries:
        validate_physical(REPO, ROOT, entry)
        validate_case(ROOT, entry, {'demo-test', 'full-test'})
        for item in [entry, *entry['candidates']]:
            label = item.get('id', 'primary')
            row = next(row for row in index['cases']
                       if row['case_id'] == entry['case_id'] and row['candidate'] == label)
            proof = ROOT / 'cases' / entry['case_id'].split('__')[-1] / 'draft-proofs' / label
            assert item['construction_sha256'] == row['construction_sha256'] == sha(ROOT / item['construction'])
            offline = item['offline']
            assert offline['exit_code'] == 0 and offline['construction_sha256'] == item['construction_sha256']
            assert sha(ROOT / offline['log']) == offline['log_sha256'] == row['offline_log_sha256']
            assert read(ROOT / offline['log'])['offline_passed'] is True
            assert 'execution-manifest.json' in offline['command']
            compat = item['compatibility']
            receipt = read(ROOT / compat['receipt'])
            assert receipt['passed'] is True and receipt['case_id'] == entry['case_id']
            assert receipt['candidate_id'] == label and receipt['construction_sha256'] == item['construction_sha256']
            assert sha(ROOT / compat['receipt']) == compat['sha256'] == row['compatibility_receipt_sha256']
            assert sha(ROOT / compat['log']) == receipt['log_sha256']
            assert sha(ROOT / compat['negative_log']) == receipt['negative_log_sha256'] == row['negative_log_sha256']
            assert 'Missing required source: interaction_history.jsonl' in (ROOT / compat['negative_log']).read_text()
            assert 'execution-manifest.json' in compat['replay_command']
            saved = read(proof / 'processing.json')
            assert saved['passed'] is True and saved['case_id'] == entry['case_id']
            assert saved['candidate_id'] == label and saved['recorded_only'] is True
            assert saved['originals_preserved'] is True and saved['physical_acceptance_claimed'] is False
            assert saved['analysis_revision']['construction_sha256'] == item['construction_sha256']
            assert sha(proof / 'processing.json') == row['saved_receipt_sha256']
            post = item['post_capture']
            assert post['recorded_only'] is True and post['test_exit_code'] == 0
            assert sha(ROOT / post['test_log']) == post['test_log_sha256'] == row['saved_log_sha256']
            assert 'execution-manifest.json' in post['command']
            evidence.append({'case_id': entry['case_id'], 'candidate': label,
                             'construction_sha256': item['construction_sha256'],
                             'compatibility_sha256': compat['sha256'],
                             'saved_sha256': row['saved_receipt_sha256']})
    return {'format': 'worker-canonical-hazard-release-cpu-check',
            'selected_cases': len(manifest['cases']), 'exact_paths': evidence,
            'physical_preparation_and_delivery_contracts_validated': True,
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
