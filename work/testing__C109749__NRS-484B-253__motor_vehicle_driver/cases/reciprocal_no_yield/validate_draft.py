"""Check current reciprocal-no-yield draft bundles and staged CPU receipts."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parents[2]
target = Path(__file__).resolve().parent
case = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_no_yield'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((target / 'draft-manifest.json').read_text())
entry = manifest['cases'][0]
assert entry['case_id'] == case and len(entry['candidates']) == 3
rows = [('primary', entry)] + [(item['id'], item) for item in entry['candidates']]
for label, item in rows:
    construction_path = target / item['construction']
    assert sha(construction_path) == item['construction_sha256']
    construction = json.loads(construction_path.read_text())
    assert construction['case_id'] == case
    files = {file['path']: file['content'] for file in construction['files']}
    config = json.loads(files['config.json'])
    assert config['selected_case_id'] == case and config['rate_hz'] == 20 and config['duration_s'] == 45
    for name, source in [('runner.py', target / 'runner.py'),
                         ('finalizer.py', target / 'finalizer.py'),
                         ('reciprocal_no_yield_observation.py', folder / 'reciprocal_no_yield_observation.py')]:
        assert files[name] == source.read_text(), (label, name)
    offline = (target / (label + '-offline.log')).read_text()
    assert '"offline_passed": true' in offline and '"simulation_started": false' in offline
    receipt_dir = target / 'proofs' / label
    compat = json.loads((receipt_dir / 'compatibility.json').read_text())
    saved = json.loads((receipt_dir / 'processing.json').read_text())
    assert compat['passed'] is True and compat['case_id'] == case and compat['candidate_id'] == label
    assert compat['construction_sha256'] == item['construction_sha256']
    assert sha(receipt_dir / 'analysis.log') == compat['log_sha256']
    assert sha(receipt_dir / 'negative-analysis.log') == compat['negative_log_sha256']
    assert 'Missing required source: interaction_history.jsonl' in (receipt_dir / 'negative-analysis.log').read_text()
    assert saved['passed'] is True and saved['recorded_only'] is True
    assert saved['native_revision']['construction_sha256'] == item['construction_sha256']
    assert saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
    print(json.dumps({'case_id': case, 'candidate': label,
                      'construction_sha256': item['construction_sha256'],
                      'offline': True, 'compatibility': True, 'negative_source_rejected': True,
                      'saved_processing': True, 'physical_acceptance_claimed': False}))
