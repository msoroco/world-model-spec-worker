"""Bind selected hydrant CPU receipts without claiming original Native observation."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / 'native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof(path):
    return {'receipt': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def compatibility(suffix, candidate):
    prefix = NATIVE / ('selected-' + suffix + '-' + candidate)
    receipt = Path(str(prefix) + '-compatibility.json')
    log = Path(str(prefix) + '-compatibility-analysis.log')
    negative = Path(str(prefix) + '-negative-analysis.log')
    assert all(path.is_file() for path in (receipt, log, negative))
    return {'receipt': str(receipt.relative_to(ROOT)),
            'log': str(log.relative_to(ROOT)),
            'negative_log': str(negative.relative_to(ROOT)),
            'sha256': sha(receipt)}


def offline(suffix, candidate, construction_sha):
    name = 'selected-' + suffix + ('-fallback1' if candidate == 'fallback1' else '')
    log = NATIVE / (name + '-offline.log')
    manifest = 'selected-fallback-compat-manifest.json' if candidate == 'fallback1' else 'selected-compat-manifest.json'
    return {'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline '
            '--manifest work/' + ROOT.name + '/' + manifest + ' --case ' + ROOT.name + '__' + suffix +
            ' --candidate ' + candidate + ' --output .runtime-work/c200568-reproof-v3-' +
            candidate + '-offline-' + suffix,
            'construction_sha256': construction_sha, 'exit_code': 0,
            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}


def main():
    manifest = json.loads((ROOT / 'selected-fallback-compat-manifest.json').read_text())
    manifest['status'] = 'cpu_proved_original_native_pending'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        entry['compatibility'] = compatibility(suffix, 'primary')
        entry['offline'] = offline(suffix, 'primary', entry['construction_sha256'])
        entry['negative'] = {'log': entry['compatibility']['negative_log'],
                             'log_sha256': sha(ROOT / entry['compatibility']['negative_log'])}
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        required = set(config['required_atoms']) | {item['name'] for item in
                                                     construction['recording_description']['channels']}
        entry['acquisition'] = {atom: {
            'entrypoint': 'runner.py',
            'method': 'Original Native actor pose, hydrant survey and synchronized four-camera frame recording; saved source join',
            'evidence': ['hydrant-trace.jsonl', 'hydrant_survey.json', 'video_frames.jsonl',
                         'trace.jsonl', 'reference_corner.mkv']}
            for atom in sorted(required)}
        fallback = entry['candidates'][0]
        fallback['compatibility'] = compatibility(suffix, 'fallback1')
        fallback['offline'] = offline(suffix, 'fallback1', fallback['construction_sha256'])
        entry['physical_preparation'] = proof(NATIVE / ('physical-' + suffix + '/physical-preparation.json'))
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        saved = NATIVE / ('selected-' + suffix + '-saved-processing.json')
        saved_log = NATIVE / ('selected-' + suffix + '-saved.log')
        assert saved.is_file() and saved_log.is_file()
        entry['post_capture'] = {
            'recorded_only': True,
            'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
            '--manifest work/' + ROOT.name + '/execution-manifest.json --case ' + case +
            ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + case,
            'test_command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
            '--manifest work/' + ROOT.name + '/selected-proof-manifest.json --case ' + case +
            ' --attempt .runtime-work/c200568-reproof-v3-primary-compat-' + suffix +
            ' --output .runtime-work/c200568-reproof-v3-saved-' + suffix +
            ' --library runtime/library --validator '
            '.runtime-work/c385967-owner-decoder/.lake/build/bin/adapterCheck',
            'test_log': str(saved_log.relative_to(ROOT)), 'test_log_sha256': sha(saved_log),
            'test_exit_code': 0, 'receipt': str(saved.relative_to(ROOT)), 'receipt_sha256': sha(saved)}
    path = ROOT / 'execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
