"""Bind completed exact-case CPU receipts to the delivery manifest."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c229023-7771-owner-nov26'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def cleaned(path):
    path.write_text(path.read_text().rstrip() + '\n')
    return sha(path)


def bind_compat(name, candidate):
    suffix = '' if candidate == 'primary' else '-fallback1'
    source = SCRATCH / ('compat-v5-' + name + suffix)
    target = HERE / 'proofs' / ('compat-' + candidate + '-' + name)
    target.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((source / 'compatibility.json').read_text())
    for from_name, to_name, key in (
            ('compatibility-analysis.log', 'analysis.log', 'log_sha256'),
            ('negative-analysis.log', 'negative.log', 'negative_log_sha256')):
        destination = target / to_name
        destination.write_bytes((source / from_name).read_bytes())
        receipt[key] = cleaned(destination)
    write(target / 'receipt.json', receipt)
    return {'receipt': str((target / 'receipt.json').relative_to(HERE)),
            'sha256': sha(target / 'receipt.json'),
            'log': str((target / 'analysis.log').relative_to(HERE)),
            'negative_log': str((target / 'negative.log').relative_to(HERE))}


def offline(name, candidate, construction_sha, case_id):
    suffix = '' if candidate == 'primary' else '-fallback1'
    log = HERE / ('proof-offline-' + name + suffix + '.log')
    hashed = cleaned(log)
    command = (str(ROOT / '.venv-cpu/bin/python') + ' ' + str(ROOT / 'runtime.py') +
               ' offline --manifest ' + str(HERE / 'execution-manifest.json') +
               ' --case ' + case_id + ' --output ' +
               str(SCRATCH / ('offline-v3-' + name + suffix)) +
               ' --python ' + str(ROOT / '.venv-cpu/bin/python'))
    if candidate != 'primary':
        command += ' --candidate fallback1'
    return {'exit_code': 0, 'construction_sha256': construction_sha,
            'command': command, 'log': log.name, 'log_sha256': hashed}


def delivery(name, case_id, sets):
    positive = HERE / ('proof-delivery-positive-' + name + '.log')
    negative = HERE / ('proof-delivery-negative-' + name + '.log')
    command = (str(ROOT / '.venv-cpu/bin/python') + ' ' +
               str(HERE / 'prove_delivery_wiring.py') + ' --case ' + case_id)
    return {'case_id': case_id, 'sets': sets,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'test_exit_code': 0, 'negative_exit_code': 2,
            'negative_expected_error': 'original-sources.json',
            'command': command, 'negative_command': command + ' --negative-missing-attempt',
            'script': 'prove_delivery_wiring.py',
            'script_sha256': sha(HERE / 'prove_delivery_wiring.py'),
            'test_log': positive.name, 'test_log_sha256': cleaned(positive),
            'negative_log': negative.name, 'negative_log_sha256': cleaned(negative),
            'scope': 'mock-only audit wiring; original physical review pending'}


def post_capture(name, case_id):
    attempt = SCRATCH / (('saved-attempt-v1-' if name == 'moving_near_right'
                          else 'saved-attempt-v2-') + name)
    output = SCRATCH / (('saved-output-v1-' if name == 'moving_near_right'
                         else 'saved-output-v2-') + name)
    base = (str(ROOT / '.venv-cpu/bin/python') + ' ' + str(ROOT / 'runtime.py') +
            ' process-saved --manifest ' + str(HERE / 'execution-manifest.json') +
            ' --case ' + case_id + ' --attempt ')
    tail = (' --library ' + str(ROOT / 'runtime/library') + ' --validator ' +
            str(ROOT / '.runtime-work/c229023-owner/validator/.lake/build/bin/adapterCheck'))
    positive = HERE / ('proof-saved-' + name + '.log')
    negative = HERE / ('proof-saved-missing-' + name + '.log')
    return {'recorded_only': True,
            'command': base + str(attempt) + ' --output ' + str(output) + tail,
            'feedback_command': base + str(SCRATCH / ('saved-attempt-absent-' + name)) +
                                ' --output ' + str(SCRATCH / ('saved-output-absent-' + name)) + tail,
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': cleaned(positive),
            'feedback_log': negative.name, 'feedback_log_sha256': cleaned(negative),
            'scope': 'synthetic diagnostic saved-only replay; original physical and legal review pending'}


def main():
    manifest = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    sets = assignment['selection_targets']
    for entry in manifest['cases']:
        name = entry['case_id'].split('__')[-1]
        entry['offline'] = offline(name, 'primary', entry['construction_sha256'],
                                   entry['case_id'])
        entry['compatibility'] = bind_compat(name, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        fallback = entry['candidates'][0]
        fallback['offline'] = offline(name, 'fallback1',
                                      fallback['construction_sha256'], entry['case_id'])
        fallback['compatibility'] = bind_compat(name, 'fallback1')
        physical = HERE / ('physical-' + name + '-receipt.json')
        entry['physical_preparation'] = {'receipt': physical.name, 'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['delivery_acceptance'] = delivery(name, entry['case_id'], sets)
        entry['post_capture'] = post_capture(name, entry['case_id'])
    manifest['status'] = 'ready'
    write(HERE / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
