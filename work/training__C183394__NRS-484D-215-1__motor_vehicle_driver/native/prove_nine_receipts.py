"""Check the final exact-case public and saved CPU receipt bindings."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
assert len(manifest['cases']) == 9
for entry in manifest['cases']:
    case = entry['case_id']
    assert entry['candidate_risk']['status'] == 'physical'
    assert len(entry['candidates']) == 1
    for candidate, selected in [('primary', entry), ('fallback1', entry['candidates'][0])]:
        construction = ROOT / selected['construction']
        assert hashlib.sha256(construction.read_bytes()).hexdigest() == selected['construction_sha256']
        assert selected['offline']['exit_code'] == 0
        offline = ROOT / selected['offline']['log']
        assert hashlib.sha256(offline.read_bytes()).hexdigest() == selected['offline']['log_sha256']
        compatibility = selected['compatibility']
        receipt = ROOT / compatibility['receipt']
        assert hashlib.sha256(receipt.read_bytes()).hexdigest() == compatibility['sha256']
        data = json.loads(receipt.read_text())
        assert data['passed'] and data['case_id'] == case
        assert data['candidate_id'] == candidate
        assert data['construction_sha256'] == selected['construction_sha256']
        assert data['measurement_keys'] == ['activation_beam_context', 'adjacent_shoulder_scope', 'lowermost_distribution_route', 'oncoming_beam_interaction']
    post = entry['post_capture']
    saved = ROOT / post['test_log']
    assert post['recorded_only'] is True and post['test_exit_code'] == 0
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == post['test_log_sha256']
    assert json.loads(saved.read_text())['passed'] is True
    physical = entry['physical_preparation']
    assert hashlib.sha256((ROOT / physical['receipt']).read_bytes()).hexdigest() == physical['sha256']
    audit = entry['delivery_acceptance']
    assert audit['case_id'] == case and audit['test_exit_code'] == 0
    assert hashlib.sha256((ROOT / audit['test_log']).read_bytes()).hexdigest() == audit['test_log_sha256']
    print('PASS', case.rsplit('__', 1)[-1], '2 offline, 2 compatibility, 1 saved, physical, audit')
