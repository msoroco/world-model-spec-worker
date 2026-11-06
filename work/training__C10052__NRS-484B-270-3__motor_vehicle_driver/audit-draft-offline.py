"""Independently check exact C10052 offline source and receipt hashes."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate
from worker_exchange.measurement_contract import validate as validate_measurement


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    summary = json.loads((HERE/'draft-offline-summary.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    assert summary['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert len(summary['results']) == 8
    expected = {(e['case_id'], candidate) for e in manifest['cases']
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    for entry in manifest['cases']:
        validate(HERE, entry, 'NRS-484B-270-3', 'C10052',
                 required=False, require_alternate=True, candidate_count=4)
        contract = json.loads((HERE/entry['measurement_contract']).read_text())
        source = json.loads((HERE/entry['construction']).read_text())
        code = next(f['content'] for f in source['files'] if f['path'] == 'finalize.py')
        validate_measurement(contract, plan['requirement_dispositions'], code, entry['case_id'])
    seen = set()
    for receipt in summary['results']:
        key = receipt['case_id'], receipt['candidate_id']
        assert key in expected and key not in seen
        seen.add(key)
        entry = next(e for e in manifest['cases'] if e['case_id'] == key[0])
        selected = entry if key[1] == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == key[1])
        assert sha(HERE/selected['construction']) == selected['construction_sha256'] == receipt['construction_sha256']
        assert receipt['exit_code'] == 0
        assert sha(HERE/receipt['command_log']) == receipt['command_log_sha256']
        assert sha(HERE/receipt['unit_log']) == receipt['unit_log_sha256']
        unit = (HERE/receipt['unit_log']).read_text()
        assert 'Ran 4 tests' in unit and '\nOK\n' in unit
        construction = json.loads((HERE/selected['construction']).read_text())
        for item in construction['files']:
            if item['path'] == 'config.json':
                continue
            path = HERE/item['path'] if item['path'].startswith('tests/') else HERE/'native'/item['path']
            assert item['content'] == path.read_text(), item['path']
    assert seen == expected
    result = {'passed': True, 'cases': 2, 'unselected_draft_candidates': 8,
              'offline_tests_per_bundle': 4, 'physical_verified': False}
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    audit()
