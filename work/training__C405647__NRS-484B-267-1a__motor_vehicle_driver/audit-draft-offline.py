"""Independent source and receipt audit of exact C405647 CPU bundles."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
CANDIDATES = {'primary', 'fallback1', 'fallback2', 'fallback3'}
SOURCES = {'runner.py', 'geometry.py', 'candidates.py', 'source-scope.json',
           'measure_saved.py', 'finalize.py', 'trigger_evidence.py'}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    summary = json.loads((FOLDER / 'draft-offline-summary.json').read_text())
    policy = json.loads((FOLDER / 'draft-construction/candidate-manifest.json').read_text())
    assert manifest['status'] == 'draft_not_selected'
    assert manifest['assignment_id'] == policy['assignment_id']
    assert manifest['runtime_manifest_sha256'] == summary['runtime_manifest_sha256']
    assert len(manifest['cases']) == 2 and len(summary['results']) == 8
    expected = {}
    hashes = set()
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        assert suffix in ('witness_1', 'witness_2')
        assert entry['kind'] == 'draft_not_selected'
        assert entry['measurement_procedure']['entrypoint'] == 'finalize.py'
        refs = [{'id': 'primary', 'construction': entry['construction'],
                 'construction_sha256': entry['construction_sha256']}, *entry['candidates']]
        assert {ref['id'] for ref in refs} == CANDIDATES
        for ref in refs:
            key = (case_id, ref['id'])
            assert key not in expected
            path = FOLDER / ref['construction']
            assert _sha(path) == ref['construction_sha256']
            assert ref['construction_sha256'] not in hashes
            hashes.add(ref['construction_sha256'])
            bundle = json.loads(path.read_text())
            assert bundle['case_id'] == case_id and bundle['cell_id'] == 'C405647'
            assert bundle['law_id'] == 'NRS-484B-267-1a'
            assert bundle['entrypoint'] == 'runner.py'
            assert bundle['status'] == 'unselected_cpu_draft'
            files = {row['path']: row['content'] for row in bundle['files']}
            assert SOURCES | {'config.json', 'tests/test_construction.py'} == set(files)
            for name in SOURCES:
                assert files[name] == (FOLDER / 'native' / name).read_text()
            config = json.loads(files['config.json'])
            assert config['case_id'] == case_id
            assert config['case_suffix'] == suffix
            assert config['candidate_id'] == ref['id']
            assert (config['duration_s'], config['rate_hz']) == (24, 20)
            assert config['status'] == 'unselected_native_runner_prototype'
            assert config['source_packets'] == []
            assert set(config['required_atoms']) == {
                'ru.emergency_vehicle', 'sig.warning_lamp', 'rel.same_direction',
                'rel.surface_gap', 'kin.position', 'rel.occupies'}
            assert bundle['measurement_plan']['status'] == 'prototype_not_runtime_compatible'
            if ref['id'] != 'primary':
                target = next(row for row in policy['cases'] if
                              row['case_suffix'] == suffix and row['candidate_id'] == ref['id'])
                assert ref['trigger']['metric'] == target['trigger']
                assert ref['changed_knobs']
            expected[key] = ref['construction_sha256']
    receipts = {(row['case_id'], row['candidate_id']): row for row in summary['results']}
    assert set(receipts) == set(expected)
    for key, receipt in receipts.items():
        assert receipt['exit_code'] == 0
        assert receipt['construction_sha256'] == expected[key]
        assert receipt['command'][2:4] == ['offline', '--manifest']
        for field, hash_field in (('command_log', 'command_log_sha256'),
                                  ('unit_log', 'unit_log_sha256')):
            assert _sha(FOLDER / receipt[field]) == receipt[hash_field]
        log = (FOLDER / receipt['unit_log']).read_text()
        assert 'Ran 2 tests' in log and '\nOK\n' in log
        assert '"carla_imported": false' in log
    return {'passed': True, 'cases': 2, 'exact_unselected_bundles': 8,
            'offline_tests_per_bundle': 2, 'selected_or_physical_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
