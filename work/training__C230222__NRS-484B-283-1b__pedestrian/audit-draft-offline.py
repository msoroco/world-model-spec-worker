"""Independent source-exact and pinned-offline receipt audit for curb drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    summary = json.loads((HERE / 'draft-offline-summary.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    if (manifest['runtime_manifest_sha256'] != batch['runtime']['source_manifest_sha256'] or
        summary['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
        manifest['status'] != 'draft_not_selected'):
        raise ValueError('Pinned runtime manifest or draft status differs')
    receipts = {(r['case_id'], r['candidate_id']): r for r in summary['results']}
    if len(receipts) != 8 or len(manifest['cases']) != 2:
        raise ValueError('Curb exact bundle count differs')
    source_names = {'runner.py', 'geometry.py', 'engineering.py', 'curb.py',
                    'finalize.py', 'road.xodr', 'tests/test_offline.py', 'config.json'}
    pair_configs = {}
    for entry in manifest['cases']:
        if entry['kind'] != 'draft_not_selected' or len(entry['candidates']) != 3:
            raise ValueError('Curb candidate row differs')
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = entry if ident == 'primary' else next(r for r in entry['candidates'] if r['id'] == ident)
            construction = HERE / ref['construction']
            if sha(construction) != ref['construction_sha256']:
                raise ValueError('Curb construction hash differs')
            bundle = json.loads(construction.read_text())
            if (bundle['case_id'], bundle['cell_id'], bundle['law_id'], bundle['actor'], bundle['entrypoint']) != (
                entry['case_id'], 'C230222', 'NRS-484B-283-1b', 'pedestrian', 'runner.py'):
                raise ValueError('Curb bundle identity differs')
            files = {f['path']: f['content'] for f in bundle['files']}
            if set(files) != source_names:
                raise ValueError('Curb bundle file set differs')
            for name in source_names - {'config.json'}:
                source = HERE / 'native' / (name.removeprefix('tests/') if name.startswith('tests/') else name)
                if files[name] != source.read_text():
                    raise ValueError('Curb bundle source differs: ' + name)
            config = json.loads(files['config.json'])
            if (config['case_id'], config['case_suffix'], config['candidate_id'],
                config['duration_s'], config['rate_hz']) != (entry['case_id'], suffix, ident, 12, 20):
                raise ValueError('Curb bundle capture contract differs')
            if len(config['cameras']) != 4 or config['source_packets']:
                raise ValueError('Curb camera or source packet contract differs')
            pair_configs[(suffix, ident)] = config
            receipt = receipts[(entry['case_id'], ident)]
            if receipt['exit_code'] != 0 or receipt['construction_sha256'] != ref['construction_sha256']:
                raise ValueError('Curb pinned offline failed')
            for log_key, hash_key in (('command_log', 'command_log_sha256'), ('unit_log', 'unit_log_sha256')):
                if sha(HERE / receipt[log_key]) != receipt[hash_key]:
                    raise ValueError('Curb offline log hash differs')
            command = (HERE / receipt['command_log']).read_text()
            unit = (HERE / receipt['unit_log']).read_text()
            if '"offline_passed": true' not in command or 'Ran 4 tests' not in unit or 'OK' not in unit:
                raise ValueError('Curb offline receipt lacks passing four-test proof')
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = pair_configs[('probe_1', ident)]
        b = pair_configs[('probe_2', ident)]
        for key in ('cameras', 'duration_s', 'rate_hz', 'required_atoms', 'cell_id', 'law_id', 'actor'):
            if a[key] != b[key]:
                raise ValueError('Curb controlled pair capture policy differs')
    return {'independent_audit': 'pass', 'exact_unselected_bundles': 8,
            'pinned_offline_receipts': 8, 'four_test_logs': 8,
            'controlled_pairs': 4, 'native_attempts': 0, 'accepted_recordings': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
