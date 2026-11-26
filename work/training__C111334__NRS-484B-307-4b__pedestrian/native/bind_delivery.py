"""Bind current exact C111334 CPU proofs into a canonical draft manifest."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
SUFFIXES = ('probe_1', 'probe_2', 'permission_before_entry')
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']
VALIDATOR = '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def clean(text):
    rows = [row.rstrip() for row in text.splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    return '\n'.join(rows) + '\n'


def bind():
    draft = read(FOLDER / 'native-draft-manifest.json')
    delivery = read(HERE / 'delivery-cpu-proof.json')['cases']
    for entry in draft['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        directory = FOLDER / 'native-selected' / suffix
        compat = directory / 'primary-compatibility.json'
        saved = directory / 'saved-positive-processing.json'
        negative = directory / 'primary-negative-analysis.log'
        physical = FOLDER / ('physical-' + suffix + '-preparation.json')
        audited = delivery[suffix]
        if (read(compat)['construction_sha256'] != entry['construction_sha256'] or
                read(physical)['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Current exact CPU proof differs: ' + suffix)
        receipt = read(directory / 'public-saved-proof.json')
        if receipt['manifest_sha256'] != sha(FOLDER / 'native-draft-manifest.json'):
            raise ValueError('Public proof binds another draft manifest: ' + suffix)
        if not read(saved)['passed'] or read(saved)['missing_evidence']:
            raise ValueError('Saved positive is not complete: ' + suffix)
        source_log = ROOT / '.runtime-work/c111334-resume' / (
            'saved-' + suffix + '-positive-v8.log')
        log = directory / 'saved-positive-command.log'
        log.write_text(clean(source_log.read_text()))
        acquisition = {
            'ru.pedestrian': {'entrypoint': 'runner.py',
                              'method': 'original Native walker identity and 600-frame trace',
                              'evidence': 'synthetic diagnostic only; original capture pending'},
            'kin.position': {'entrypoint': 'runner.py',
                             'method': 'original Native pedestrian pose and body samples',
                             'evidence': 'synthetic diagnostic only; original capture pending'},
            'kin.heading': {'entrypoint': 'runner.py',
                            'method': 'original Native walker heading and frame clock',
                            'evidence': 'synthetic diagnostic only; original capture pending'},
            'rel.occupies': {'entrypoint': 'selected_finalize.py',
                             'method': 'pedestrian body polygon overlap with authored highway corridor',
                             'evidence': 'synthetic diagnostic only; original capture pending'},
            'pedestrian_entry': {'entrypoint': 'selected_finalize.py',
                                 'method': '600-frame Native, four-camera and independent device review join',
                                 'evidence': 'synthetic diagnostic only; original pixel review pending'},
        }
        entry.update({
            'candidate_risk': {
                'status': 'none',
                'reason': 'The authored crossing has four fixed complementary camera angles and no identified map occluder or specific trajectory failure; physical visibility and signal realization still require local review.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'acquisition': acquisition,
            'compatibility': {'receipt': 'native-selected/' + suffix + '/primary-compatibility.json',
                              'sha256': sha(compat),
                              'log': 'native-selected/' + suffix + '/primary-compatibility-analysis.log',
                              'negative_log': 'native-selected/' + suffix + '/primary-negative-analysis.log'},
            'negative': {'log': 'native-selected/' + suffix + '/primary-negative-analysis.log'},
            'saved_processing': {'receipt': 'native-selected/' + suffix + '/saved-positive-processing.json',
                                 'sha256': sha(saved)},
            'physical_preparation': {'receipt': physical.name,
                                     'sha256': sha(physical)},
            'post_capture': {'recorded_only': True,
                             'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                                        FOLDER.name + '/execution-manifest.json --case ' + case +
                                        ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                                        ' --library runtime/library --validator ' + VALIDATOR,
                             'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                             'test_exit_code': 0,
                             'test_log': 'native-selected/' + suffix + '/saved-positive-command.log',
                             'test_log_sha256': sha(log)},
            'delivery_acceptance': {
                'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
                'script': audited['script'],
                'script_sha256': audited['script_sha256'],
                'command': audited['positive_command'],
                'test_exit_code': audited['positive_exit_code'],
                'test_log': audited['positive_log'],
                'test_log_sha256': audited['positive_log_sha256'],
                'negative_command': audited['negative_command'],
                'negative_exit_code': audited['negative_exit_code'],
                'negative_expected_error': audited['negative_expected_error'],
                'negative_log': audited['negative_log'],
                'negative_log_sha256': audited['negative_log_sha256'],
                'proof_scope': 'Synthetic source join and rejection as original only',
            },
        })
    draft['status'] = 'cpu_delivery_draft_physical_unverified'
    draft.pop('delivery_ready', None)
    target = FOLDER / 'execution-manifest.json'
    write(target, draft)
    return {'cases': len(draft['cases']), 'manifest_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps(bind(), sort_keys=True))
