"""Independent exact-hash, law/context and pinned offline receipt audit."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(FOLDER / 'native'))
from worker_exchange.candidate_constructions import validate
from worker_exchange.measurement_contract import validate as validate_measurement
from engineering import parameters


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    summary = json.loads((FOLDER / 'draft-offline-summary.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    if manifest['status'] != 'draft_not_selected' or len(manifest['cases']) != 2:
        raise AssertionError('Selected or missing draft cases')
    if len(summary['results']) != 8:
        raise AssertionError('Missing exact offline receipts')
    expected = set()
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        validate(FOLDER, entry, 'NRS-484B-403-2', 'C104538',
                 required=False, require_alternate=True, candidate_count=4)
        contract = json.loads((FOLDER / entry['measurement_contract']).read_text())
        construction = json.loads((FOLDER / entry['construction']).read_text())
        analysis = next(f['content'] for f in construction['files'] if f['path'] == 'finalize.py')
        validate_measurement(contract, plan['requirement_dispositions'], analysis, entry['case_id'])
        primary = parameters(suffix, 'primary')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
            path = FOLDER / source['construction']
            if digest(path) != source['construction_sha256']:
                raise AssertionError('Changed exact construction')
            embedded = json.loads(path.read_text())['files']
            for item in embedded:
                if item['path'] == 'config.json':
                    config = json.loads(item['content'])
                    if config['case_id'] != entry['case_id'] or config['candidate_id'] != candidate:
                        raise AssertionError('Candidate config differs from exact identity')
                else:
                    native = FOLDER / ('native/' + Path(item['path']).name) if item['path'].startswith('tests/') else FOLDER / item['path']
                    if item['path'] in ('runner.py', 'geometry.py', 'controller.py', 'engineering.py',
                                        'measure_u_turn.py', 'finalize.py', 'cameras.py'):
                        native = FOLDER / 'native' / item['path']
                    if native.read_text() != item['content']:
                        raise AssertionError('Embedded source differs: ' + item['path'])
            policy = parameters(suffix, candidate)
            if policy['native_route_xy_m'] != primary['native_route_xy_m'] or policy['law_id'] != primary['law_id']:
                raise AssertionError('Candidate changed legal route/context')
            if candidate == 'fallback1' and not policy['target_speed_mps'] < primary['target_speed_mps']:
                raise AssertionError('Speed fallback ineffective')
            if candidate == 'fallback2' and not policy['lookahead_m'] > primary['lookahead_m']:
                raise AssertionError('Lookahead fallback ineffective')
            if candidate == 'fallback3' and policy['sign_camera_xyz_m'] == primary['sign_camera_xyz_m']:
                raise AssertionError('Sign camera fallback ineffective')
            expected.add((entry['case_id'], candidate))
    observed = set()
    for receipt in summary['results']:
        key = receipt['case_id'], receipt['candidate_id']
        if key in observed or key not in expected or receipt['exit_code'] != 0:
            raise AssertionError('Missing, duplicated or failed offline receipt')
        observed.add(key)
        entry = next(e for e in manifest['cases'] if e['case_id'] == key[0])
        source = entry if key[1] == 'primary' else next(c for c in entry['candidates'] if c['id'] == key[1])
        if receipt['construction_sha256'] != source['construction_sha256']:
            raise AssertionError('Offline receipt used another construction')
        for path_key, hash_key in (('command_log','command_log_sha256'), ('unit_log','unit_log_sha256')):
            if digest(FOLDER / receipt[path_key]) != receipt[hash_key]:
                raise AssertionError('Offline log hash changed')
        unit = (FOLDER / receipt['unit_log']).read_text()
        if 'Ran 15 tests' not in unit or '\nOK\n' not in unit:
            raise AssertionError('Exact bundle tests did not pass')
    if observed != expected:
        raise AssertionError('Exact bundle inventory incomplete')
    return {'passed': True, 'cases': 2, 'unselected_candidates': 8,
            'offline_tests_per_bundle': 15, 'native_executed': False,
            'selected_delivery_cases': 0}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
