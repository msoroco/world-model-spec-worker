"""Bind six selected CPU proofs to a stable exact-case execution manifest."""

import hashlib
import json
import os
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    preflight_path = ROOT / 'selected-preflight-manifest.json'
    preflight = read(preflight_path)
    indexed = []
    for path, key in (('selected-offline/index.json', 'checks'),
                      ('compatibility/index.json', 'passed'),
                      ('recorded-only/index.json', 'passed'),
                      ('delivery-audit/index.json', 'cases')):
        indexed.append({row['case_id']: row for row in read(ROOT / path)[key]})
    offline, compatible, saved, audit = indexed
    manifest_sha = sha(preflight_path)
    entries = []
    for source in preflight['cases']:
        entry = dict(source)
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        off, com, rec, aud = (index[case] for index in indexed)
        if off['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Exact offline proof changed: ' + suffix)
        receipt = ROOT / com['receipt']
        if (sha(receipt) != com['receipt_sha256'] or
                read(receipt)['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Compatibility receipt changed: ' + suffix)
        tokens = shlex.split(com['command'])
        attempt = Path(tokens[tokens.index('--output') + 1])
        if read(attempt / 'candidate-selection.json').get('manifest_sha256') != manifest_sha:
            raise ValueError('Compatibility attempt binds another selected manifest')
        proof = ROOT / rec['proof']
        if (sha(proof) != rec['proof_sha256'] or
                read(proof).get('manifest_sha256') != manifest_sha):
            raise ValueError('Recorded-only proof changed: ' + suffix)
        physical = ROOT / 'physical' / suffix / 'receipt.json'
        entry['offline'] = off
        entry['compatibility'] = {'receipt': com['receipt'], 'sha256': com['receipt_sha256'],
                                  'log': com['analysis_log'], 'negative_log': com['negative_log']}
        entry['negative'] = {'log': com['negative_log'], 'log_sha256': com['negative_sha256']}
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(ROOT)),
                                         'sha256': sha(physical)}
        survey = '.runtime-work/original-surveys/' + preflight['assignment_id'] + '/' + case + '/context-survey.json'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT',
                                   'survey_env_var': 'SCENARIO_CONTEXT_SURVEY',
                                   'survey_path': survey,
                                   'capture_command_prefix': 'SCENARIO_CONTEXT_SURVEY=' + survey,
                                   'execute_command_prefix': 'SCENARIO_CONTEXT_SURVEY=' + survey}
        entry['acquisition'] = {
            'native_signal_reference_body_and_conflict': {'entrypoint': 'capture.py',
                'method': 'original Native signal, body, reference and conflict joined by frame',
                'evidence': ['native.jsonl', 'geometry.json', 'context-survey.json', 'video_frames.jsonl']},
            'four_camera_video': {'entrypoint': 'capture.py',
                'method': 'four original synchronized RGB streams',
                'evidence': ['overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                             'driver_reference.mkv', 'video_frames.jsonl']}}
        recorded = read(proof)
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + preflight['assignment_id'] +
                       '/execution-manifest.json --case ' + case +
                       ' --attempt $ORIGINAL_ATTEMPT --output $DERIVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR',
            'feedback_command': 'test -f $DERIVED_OUTPUT/v0001/feedback.json && cat $DERIVED_OUTPUT/v0001/feedback.json',
            'test_exit_code': recorded['test_exit_code'],
            'test_log': recorded['test_log'], 'test_log_sha256': recorded['test_log_sha256']}
        entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            **{key: aud[key] for key in ('script', 'script_sha256', 'command',
                                         'test_exit_code', 'test_log', 'test_log_sha256',
                                         'negative_command', 'negative_exit_code',
                                         'negative_expected_error', 'negative_log',
                                         'negative_log_sha256')}}
        entry['preparation_status'] = 'cpu_proven_original_delivery_pending'
        entry['delivery_readiness'] = 'cpu_prepared_original_capture_pending'
        entries.append(entry)
    final = {'format': 'worker-execution-manifest',
             'assignment_id': preflight['assignment_id'],
             'runtime_manifest_sha256': preflight['runtime_manifest_sha256'],
             'cases': entries}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    staged = SCRATCH / 'c111271-execution-manifest.staging'
    staged.write_text(json.dumps(final, indent=2) + '\n')
    target = ROOT / 'execution-manifest.json'
    os.replace(staged, target)
    print(json.dumps({'exact_cases': len(entries), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
