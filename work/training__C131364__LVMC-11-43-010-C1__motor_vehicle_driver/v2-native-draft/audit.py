"""Audit CPU proofs for the unselected Native execution draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = CASE / 'v2-native-draft-manifest.json'
manifest = json.loads(manifest_path.read_text())
assert manifest['status'] == 'native_execution_draft_unselected'
assert len(manifest['cases']) == 2
results = []
for entry in manifest['cases']:
    witness = entry['case_id'].rsplit('__', 1)[-1]
    construction_path = CASE / entry['construction']
    construction = json.loads(construction_path.read_text())
    proof = HERE / witness / 'proofs'
    compatibility = json.loads((proof / 'compatibility.json').read_text())
    processing = json.loads((proof / 'processing.json').read_text())
    assert construction['entrypoint'] == 'runner.py'
    files = {item['path']: item['content'] for item in construction['files']}
    assert files['runner.py'] == (CASE / 'native/v2_native_capture.py').read_text()
    assert files['v2_runner.py'] == (CASE / 'native/v2_runner.py').read_text()
    assert sha(construction_path) == entry['construction_sha256']
    assert compatibility['passed'] is True and len(compatibility['checks']) == 11
    assert compatibility['case_id'] == entry['case_id']
    assert compatibility['construction_sha256'] == entry['construction_sha256']
    assert compatibility['analysis_report_sha256'] == sha(proof / 'analysis-report.json')
    assert compatibility['negative_log_sha256'] == sha(proof / 'negative-analysis.log')
    assert compatibility['negative_error_contains'] in (proof / 'negative-analysis.log').read_text()
    assert 'Ran 4 tests' in (proof / 'offline.log').read_text()
    assert processing['passed'] and processing['recorded_only']
    assert processing['native_revision']['construction_sha256'] == entry['construction_sha256']
    assert not processing['physical_acceptance_claimed']
    results.append({'case_id': entry['case_id'],
        'construction_sha256': entry['construction_sha256'],
        'compatibility_sha256': sha(proof / 'compatibility.json'),
        'processing_sha256': sha(proof / 'processing.json')})
print(json.dumps({'passed': True, 'manifest_sha256': sha(manifest_path),
    'cases': results, 'physical_acceptance_claimed': False}))
