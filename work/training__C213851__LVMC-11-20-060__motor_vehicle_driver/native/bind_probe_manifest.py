"""Bind passed exact CPU receipts while preserving a partial delivery status."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = ROOT / 'probe-manifest.json'
    manifest = json.loads(path.read_text())
    manifest['status'] = 'partial'
    manifest['delivery_ready'] = False
    manifest['comparison_audits'] = [{
        'comparison_id': AID + '__comparison',
        'case_ids': [AID + '__stop_before_sidewalk',
                     AID + '__cross_without_stop'],
        'result': 'native/selected-comparison.json',
        'result_sha256': sha(NATIVE / 'selected-comparison.json'),
        'log': 'native/selected-comparison.log',
        'log_sha256': sha(NATIVE / 'selected-comparison.log'),
    }]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        base = NATIVE / suffix
        relative = 'native/' + suffix
        receipt = base / 'compatibility/compatibility.json'
        entry.update({
            'kind': 'delivery',
            'native_handoff': {
                'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST',
                'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {
                'status': 'none',
                'reason': 'No original Native physical failure has been measured;'
                          ' original topology and pixel review remain required.'},
            'candidates': [],
            'offline': {
                'exit_code': 0,
                'construction_sha256': entry['construction_sha256'],
                'command': '.venv-cpu/bin/python -B runtime.py offline '
                           f'--manifest work/{AID}/native/probe-offline-manifest.json '
                           f'--case {entry["case_id"]} '
                           '--output .runtime-work/c213851-exact-offline '
                           '--python $PWD/.venv-cpu/bin/python',
                'log': relative + '/offline.log',
                'log_sha256': sha(base / 'offline.log')},
            'compatibility': {
                'receipt': relative + '/compatibility/compatibility.json',
                'sha256': sha(receipt),
                'log': relative + '/compatibility/compatibility-analysis.log',
                'negative_log':
                    relative + '/compatibility/negative-analysis.log'},
            'negative': {
                'log': relative + '/compatibility/negative-analysis.log'},
        })
        construction = json.loads((base / 'construction.json').read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        needed = set(config['required_atoms']) | {
            channel['name'] for channel in
            construction['recording_description']['channels']}
        entry['acquisition'] = {
            name: {'entrypoint': 'native/runner.py',
                   'method': 'original 20 Hz Native/Core frame and source join',
                   'evidence': 'sealed trace, capture evidence and four cameras'}
            for name in sorted(needed)}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest_sha256': sha(path), 'case_count': len(manifest['cases']),
            'status': manifest['status']}


if __name__ == '__main__':
    print(json.dumps(bind()))
