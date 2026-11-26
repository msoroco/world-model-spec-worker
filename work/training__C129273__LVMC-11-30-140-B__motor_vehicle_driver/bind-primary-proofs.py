"""Bind exact current-runtime primary CPU receipts to the selected manifest."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIXES = ('probe_1', 'probe_2', 'white_wholly', 'white_partial',
            'assisted', 'early_release')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'partial'
    for entry, suffix in zip(manifest['cases'], SUFFIXES):
        case = ASSIGNMENT + '__' + suffix
        if entry['case_id'] != case:
            raise ValueError('Exact case order changed')
        proof = ROOT / '.runtime-work' / ('c129273-compat-' + suffix + '-v7')
        offline = ROOT / '.runtime-work' / ('c129273-offline-' + suffix + '-v7')
        receipt = json.loads((proof / 'compatibility.json').read_text())
        if (receipt['passed'] is not True or receipt['case_id'] != case or
                receipt['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Public compatibility proof differs: ' + suffix)
        if not (offline / 'offline.log').is_file():
            raise ValueError('Exact offline log absent: ' + suffix)
        offline_target = HERE / 'offline' / (suffix + '-primary.log')
        copy(offline / 'offline.log', offline_target)
        receipt_target = HERE / 'compatibility' / (suffix + '-primary.json')
        analysis_target = HERE / 'compatibility' / (suffix + '-primary-analysis.log')
        negative_target = HERE / 'compatibility' / (suffix + '-primary-negative.log')
        copy(proof / 'compatibility.json', receipt_target)
        copy(proof / 'compatibility-analysis.log', analysis_target)
        copy(proof / 'negative-analysis.log', negative_target)
        if (sha(analysis_target) != receipt['log_sha256'] or
                sha(negative_target) != receipt['negative_log_sha256']):
            raise ValueError('Public log differs: ' + suffix)
        entry['offline'] = {
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' +
                       ASSIGNMENT + '/draft-execution-manifest.json --case ' + case +
                       ' --output .runtime-work/c129273-offline-' + suffix + '-v7',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': str(offline_target.relative_to(HERE)),
            'log_sha256': sha(offline_target)}
        entry['compatibility'] = {'receipt': str(receipt_target.relative_to(HERE)),
                                  'sha256': sha(receipt_target),
                                  'log': str(analysis_target.relative_to(HERE)),
                                  'negative_log': str(negative_target.relative_to(HERE))}
        entry['negative'] = {'log': str(negative_target.relative_to(HERE))}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['delivery_readiness'] = 'incomplete'
        entry['acquisition'] = {
            'vehicle_person_pose': {
                'entrypoint': 'runner.py',
                'method': 'same-tick original Native vehicle/person pose, speed, body box and four-camera capture followed by recorded-only derivation',
                'evidence': 'vehicle-person-poses.jsonl, video_frames.jsonl, camera-frames.jsonl, blind-person-context.json'},
            'blind_person_source_context': {
                'entrypoint': 'runner.py',
                'method': 'retained marker, blindness, assistant and driver requests with original source review flags',
                'evidence': 'blind-person-context.json, road-survey.json, four original camera videos'},
        }
        construction = json.loads((HERE / entry['construction']).read_text())
        for channel in construction['recording_description']['channels']:
            entry['acquisition'].setdefault(channel['name'], {
                'entrypoint': 'runner.py',
                'method': channel['method'] + '; original source and pixel review required',
                'evidence': 'vehicle-person-poses.jsonl, blind-person-context.json, road-survey.json, four original camera videos',
            })
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    chosen = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    (HERE / 'construction.json').write_text(json.dumps(chosen, indent=2) + '\n')
    for item in chosen['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    print(json.dumps({'selected': len(manifest['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
