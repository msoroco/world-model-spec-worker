"""Bind current nine-case delivery and reciprocal comparison diagnostic proofs."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
manifest_path = folder / 'execution-manifest.json'
aid = folder.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


manifest = json.loads(manifest_path.read_text())
root = manifest['cases'][0]['delivery_acceptance']
root['command'] = (f'.venv-cpu/bin/python work/{aid}/delivery_fixture_proof.py '
                   f'--case {root["case_id"]} '
                   '--output-root .runtime-work/c109749-nine-case-root-delivery-positive-v1')
root['negative_command'] = (f'.venv-cpu/bin/python work/{aid}/delivery_fixture_proof.py '
                            f'--case {root["case_id"]} '
                            '--output-root .runtime-work/c109749-nine-case-root-delivery-negative-v1 '
                            '--negative-source-root .runtime-work/c109749-nine-case-root-delivery-positive-v1')
root['test_log_sha256'] = sha(folder / root['test_log'])
root['negative_log_sha256'] = sha(folder / root['negative_log'])
for entry in manifest['cases'][-2:]:
    suffix = entry['case_id'].split('__')[-1]
    proof = json.loads((folder / 'cases' / suffix / 'delivery-proof-receipt.json').read_text())
    accept = entry['delivery_acceptance']
    accept['command'] = proof['positive']['command']
    positive_root = accept['command'].split('--output-root ', 1)[1]
    negative_root = ('.runtime-work/c109749-reciprocal-yield-matched-delivery-negative-v1'
                     if suffix == 'reciprocal_yield_matched' else
                     '.runtime-work/c109749-reciprocal-no-yield-delivery-negative-v1')
    accept['negative_command'] = (
        f'PYTHONPATH=work/{aid} .venv-cpu/bin/python work/{aid}/cases/{suffix}/delivery_fixture_proof.py '
        f'--case {entry["case_id"]} --output-root {negative_root} '
        f'--negative-source-root {positive_root}')
    accept['negative_expected_error'] = proof['negative']['expected_error']
    accept['test_log_sha256'] = sha(folder / accept['test_log'])
    accept['negative_log_sha256'] = sha(folder / accept['negative_log'])
write(manifest_path, manifest)

receipt_path = folder / 'comparison-proofs/receipt.json'
receipt = json.loads(receipt_path.read_text())
receipt['command'] = receipt['command'].replace('c109749-seven-case-', 'c109749-nine-case-')
receipt['negative_command'] = receipt['negative_command'].replace('c109749-seven-case-', 'c109749-nine-case-')
for field, source in [('log_sha256', 'log'), ('result_sha256', 'result'),
                      ('negative_log_sha256', 'negative_log')]:
    receipt[field] = sha(folder / receipt[source])
write(receipt_path, receipt)
print(json.dumps({'canonical_cases': len(manifest['cases']),
                  'root_delivery_rebound': True, 'reciprocal_comparison_rebound': True}))
