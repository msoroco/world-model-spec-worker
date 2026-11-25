"""Bind selected exact-case CPU receipts to the canonical delivery manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return path.relative_to(HERE).as_posix()


def receipt_refs(case, candidate):
    prefix = case + '-' + ('' if candidate == 'primary' else candidate + '-')
    proof = HERE / 'selected-proofs'
    compatibility = proof / (prefix + 'compatibility.json')
    analysis = proof / (prefix + 'analysis.log')
    negative = proof / (prefix + 'negative.log')
    processing = proof / (prefix + 'processing.json')
    public = json.loads(compatibility.read_text())
    saved = json.loads(processing.read_text())
    if (public['case_id'] != HERE.name + '__' + case or
            public['candidate_id'] != candidate or not public['passed'] or
            public['log_sha256'] != sha(analysis) or
            public['negative_log_sha256'] != sha(negative) or
            not saved['passed'] or not saved['recorded_only'] or
            saved['timestamp_joins']['frames'] != 600 or
            saved['physical_acceptance_claimed'] is not False):
        raise ValueError('Public/saved receipt mismatch: ' + case + '/' + candidate)
    return ({'receipt': ref(compatibility), 'sha256': sha(compatibility),
             'log': ref(analysis), 'negative_log': ref(negative)},
            {'receipt': ref(processing), 'sha256': sha(processing)})


def offline(case_id, case, candidate, construction_hash):
    log = HERE / 'native' / (f'selected-offline-{case}-{candidate}-v' +
                             ('3' if candidate == 'primary' else '2') + '.log')
    output = '.runtime-work/c230241-selected-offline-' + case + '-' + candidate + '-v' + (
        '3' if candidate == 'primary' else '2')
    command = (f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/selected-probe-manifest.json '
               f'--case {case_id} --candidate {candidate} --output {output} '
               f'--python {ROOT / ".venv-cpu/bin/python"}')
    return {'command': command, 'exit_code': 0, 'construction_sha256': construction_hash,
            'log': ref(log), 'log_sha256': sha(log)}


def delivery(case_id, case):
    script = HERE / 'delivery_audit.py'
    positive = HERE / 'delivery-proof' / (case + '-positive.log')
    negative = HERE / 'delivery-proof' / (case + '-negative.log')
    command = f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py --case {case_id}'
    return {'case_id': case_id, 'sets': ['full-train'], 'checks': CHECKS,
            'script': ref(script), 'script_sha256': sha(script),
            'command': command + ' --diagnostic', 'test_exit_code': 0,
            'test_log': ref(positive), 'test_log_sha256': sha(positive),
            'negative_command': command, 'negative_exit_code': 1,
            'negative_expected_error': 'Original Native lamp pixels and calibrated reach required for delivery acceptance',
            'negative_log': ref(negative), 'negative_log_sha256': sha(negative)}


def main():
    data = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    for entry in data['cases']:
        case_id = entry['case_id']
        case = case_id.rsplit('__', 1)[-1]
        entry['kind'] = 'delivery'
        entry['id'] = 'primary'
        entry['offline'] = offline(case_id, case, 'primary', entry['construction_sha256'])
        entry['compatibility'], saved = receipt_refs(case, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        entry['saved_processing'] = saved
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        physical = HERE / 'physical-proof' / case / 'proof.json'
        entry['physical_preparation'] = {'case_id': case_id,
                                         'receipt': ref(physical), 'sha256': sha(physical)}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        required = set(config['required_atoms']) | {
            item['name'] for item in construction['recording_description']['channels']}
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py',
                   'method': 'sample original Native body, lamp, range, frame and four camera channels at 20 Hz',
                   'evidence': 'native-lighting-frames.jsonl, lighting-review.jsonl, video_frames.jsonl and original camera videos'}
            for name in sorted(required)}
        entry['post_capture'] = {
            'recorded_only': True,
            'command': (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json '
                        f'--case {case_id} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" '
                        '--library runtime/library --validator "$DECODER"'),
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': saved['receipt'],
            'test_log_sha256': saved['sha256']}
        entry['delivery_acceptance'] = delivery(case_id, case)
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate['offline'] = offline(case_id, case, ident,
                                           candidate['construction_sha256'])
            candidate['compatibility'], candidate['saved_processing'] = receipt_refs(case, ident)
            candidate['negative'] = {'log': candidate['compatibility']['negative_log']}
    data['format'] = 'worker-execution-manifest'
    data['status'] = 'selected_delivery_prepared'
    (HERE / 'execution-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'cases': len(data['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
