"""Independent audit of exact unselected C405647 1(b) pinned offline receipts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
NATIVE = FOLDER / 'native'
SOURCES = {'runner.py', 'build.py', 'measure_saved.py', 'prepare_original.py'}
CANDIDATES = {'primary', 'fallback1', 'fallback2', 'fallback3'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    summary = json.loads((FOLDER / 'draft-offline-summary.json').read_text())
    draft = json.loads((NATIVE / 'drafts' / 'manifest.json').read_text())
    if (manifest['status'] != 'draft_not_selected' or
        manifest['assignment_id'] != FOLDER.name or
        draft['assignment_id'] != FOLDER.name or
        manifest['runtime_manifest_sha256'] != summary['runtime_manifest_sha256'] or
        len(manifest['cases']) != 2 or len(summary['results']) != 8):
        raise ValueError('offline manifest identity or coverage differs')
    expected = {}
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        if suffix not in ('reference', 'contrast') or entry['kind'] != 'draft_not_selected':
            raise ValueError('wrong controlled case')
        refs = [{'id': 'primary', 'construction': entry['construction'],
                 'construction_sha256': entry['construction_sha256']}, *entry['candidates']]
        if {ref['id'] for ref in refs} != CANDIDATES:
            raise ValueError('four distinct candidates absent')
        for ref in refs:
            key = (case_id, ref['id'])
            path = FOLDER / ref['construction']
            if key in expected or sha(path) != ref['construction_sha256']:
                raise ValueError('construction hash or uniqueness differs')
            bundle = json.loads(path.read_text())
            if (bundle['case_id'] != case_id or bundle['law_id'] != 'NRS-484B-267-1b' or
                bundle['cell_id'] != 'C405647' or bundle['actor'] != 'motor_vehicle_driver' or
                bundle['entrypoint'] != 'runner.py' or bundle['status'] != 'unselected_cpu_draft'):
                raise ValueError('construction identity differs')
            files = {item['path']: item['content'] for item in bundle['files']}
            if set(files) != SOURCES | {'assignment-source.json', 'road.xodr', 'requested-tracks.jsonl',
                                       'native-requests.jsonl', 'config.json',
                                       'tests/test_construction.py'}:
                raise ValueError('construction source set differs')
            for name in SOURCES:
                if files[name] != (NATIVE / name).read_text():
                    raise ValueError('construction source stale')
            if files['assignment-source.json'] != (FOLDER.parents[1] / 'inputs' / FOLDER.name / 'assignment.json').read_text():
                raise ValueError('bundled frozen assignment source differs')
            if files['road.xodr'] != (NATIVE / 'drafts' / 'road.xodr').read_text():
                raise ValueError('construction map stale')
            for name in ('requested-tracks.jsonl', 'native-requests.jsonl'):
                if files[name] != (NATIVE / 'drafts' / suffix / ref['id'] / name).read_text():
                    raise ValueError('construction track stale')
            config = json.loads(files['config.json'])
            if (config['case_id'] != case_id or config['candidate_id'] != ref['id'] or
                config['case_suffix'] != suffix or config['status'] != 'unselected_native_runner_prototype' or
                (config['duration_s'], config['rate_hz']) != (24, 20) or
                config['source_packets'] != [] or config['physical_execution_or_legal_outcome_verified']):
                raise ValueError('config identity or physical status differs')
            if set(config['required_atoms']) != {'rel.same_direction', 'rel.surface_gap',
                                                  'kin.position', 'rel.occupies'}:
                raise ValueError('unsupported required atom')
            if ref['id'] != 'primary':
                draft_config = json.loads((NATIVE / 'drafts' / suffix / ref['id'] / 'config.json').read_text())
                if ref['trigger']['metric'] != draft_config['measured_trigger']['metric'] or not ref['trigger']['triggered']:
                    raise ValueError('measured fallback trigger differs')
            expected[key] = ref['construction_sha256']
    receipts = {(r['case_id'], r['candidate_id']): r for r in summary['results']}
    if set(receipts) != set(expected):
        raise ValueError('offline receipts missing')
    for key, receipt in receipts.items():
        if receipt['exit_code'] != 0 or receipt['construction_sha256'] != expected[key]:
            raise ValueError('offline case failed or construction changed')
        for field, hash_field in (('command_log', 'command_log_sha256'),
                                  ('unit_log', 'unit_log_sha256')):
            if sha(FOLDER / receipt[field]) != receipt[hash_field]:
                raise ValueError('offline log hash differs')
        log = (FOLDER / receipt['unit_log']).read_text()
        if 'Ran 3 tests' not in log or '\nOK\n' not in log or '"carla_imported": false' not in log:
            raise ValueError('offline unit evidence differs')
    result = {'format': 'c405647-1b-independent-offline-audit-v1',
              'manifest_sha256': sha(FOLDER / 'draft-execution-manifest.json'),
              'summary_sha256': sha(FOLDER / 'draft-offline-summary.json'),
              'exact_bundles': 8, 'tests_per_bundle': 3,
              'selected_or_physical_claimed': False}
    (FOLDER / 'draft-offline-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
