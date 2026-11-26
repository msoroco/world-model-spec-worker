"""Bind pinned synthetic CPU receipts into source-gated passenger-zone draft."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    diagnostic = json.loads((HERE / 'execution-manifest.compatibility-diagnostic.json').read_text())
    entries = []
    for original in diagnostic['cases']:
        name = original['case_id'].removeprefix(AID + '__')
        source = ROOT / '.runtime-work' / 'c150116-new' / ('compat-' + name + '-v5')
        target = HERE / 'proofs' / ('selected-' + name)
        target.mkdir(parents=True, exist_ok=True)
        for src, dst in [('compatibility.json', 'receipt.json'),
                         ('compatibility-analysis.log', 'analysis.log'),
                         ('negative-analysis.log', 'negative.log')]:
            if not (source / src).is_file():
                raise ValueError('pinned compatibility output missing: ' + name + '/' + src)
            shutil.copyfile(source / src, target / dst)
        construction = json.loads((HERE / original['construction']).read_text())
        acquisition = {channel['name']: {'entrypoint': 'analysis.py',
                                         'method': channel['method'],
                                         'evidence': 'channel-' + channel['name'] + '.jsonl'}
                       for channel in construction['recording_description']['channels']}
        entries.append({**original, 'kind': 'delivery',
                        'source_gate': 'reviewed original zone marking, applicable regulation, civil clock, passenger event and expeditious judgment sweeps absent',
                        'acquisition': acquisition,
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'compatibility': {'receipt': str((target / 'receipt.json').relative_to(HERE)),
                                          'sha256': sha(target / 'receipt.json'),
                                          'log': str((target / 'analysis.log').relative_to(HERE))},
                        'negative': {'log': str((target / 'negative.log').relative_to(HERE))},
                        'offline': {'construction_sha256': original['construction_sha256'],
                                    'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID + '/execution-manifest.json --case ' + original['case_id'] + ' --output .runtime-work/c150116-new/selected-offline-' + name,
                                    'exit_code': None,
                                    'log': 'cpu-nov25-selected-offline-' + name + '.log',
                                    'log_sha256': None},
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Curb zone marking, parked ego and passenger event may not remain visible together in original camera views; original curb geometry and sightlines need physical review before selecting a fallback.'},
                        'candidates': []})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': AID, 'status': 'source_gated_draft',
                'runtime_manifest_sha256': diagnostic['runtime_manifest_sha256'],
                'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
