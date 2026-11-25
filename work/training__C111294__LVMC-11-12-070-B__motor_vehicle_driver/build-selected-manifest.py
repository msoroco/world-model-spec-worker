"""Bind the two proved constructions to exact selected case identities.

This is an incremental CPU handoff. Independent acceptance and branch review
remain separate and are not asserted by this manifest.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
RUNTIME = hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest()


def digest(path):
    return hashlib.sha256((HERE / path).read_bytes()).hexdigest()


def evidence(path):
    return {'receipt': path, 'sha256': digest(path)}


def compatibility(number, candidate):
    stem = f'selected-probe-{number}-{candidate}' if candidate != 'primary' else f'current-v2-probe-{number}'
    if candidate == 'primary':
        receipt = f'{stem}-compatibility.json'
        analysis = f'{stem}-compatibility-analysis.log'
        negative = f'{stem}-negative-analysis.log'
    else:
        receipt = f'{stem}-compatibility.json'
        analysis = f'{stem}-analysis.log'
        negative = f'{stem}-negative.log'
    if not (HERE / receipt).is_file():
        return None
    return {'receipt': receipt, 'sha256': digest(receipt),
            'log': analysis, 'negative_log': negative}


def one(number):
    case = f'{ASSIGNMENT}__probe_{number}'
    primary = 'draft-primary' if number == 1 else 'draft-controlled'
    primary_path = f'{primary}/construction.json'
    fallback_path = f'cases/probe_{number}/fallback1/construction.json'
    source_trigger = {
        'source': 'original Native road, full-body poses and native_samples.jsonl',
        'metric': 'through body position at the first requested hold, before entrant clearing',
        'failure_condition': 'observed full through body overshoots the source-reviewed hold location before the entrant clears',
    }
    primary_offline = f'native-live-probe-{number}-offline.log'
    fallback_offline = f'fallback-probe-{number}-offline.log'
    candidate = {
        'id': 'fallback1', 'construction': fallback_path,
        'construction_sha256': digest(fallback_path),
        'trigger': source_trigger,
        'changed_knobs': ['through authored upstream start 65 m to 70 m; fixed road, entrant, controller and capture contract retained'],
        'offline': {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c111294-selected-probe-{number}-fallback-offline --python $PWD/.venv-cpu/bin/python',
                    'exit_code': 0, 'construction_sha256': digest(fallback_path),
                    'log': fallback_offline, 'log_sha256': digest(fallback_offline)},
    }
    candidate_proof = compatibility(number, 'fallback1')
    if candidate_proof:
        candidate['compatibility'] = candidate_proof
    entry = {
        'case_id': case, 'kind': 'delivery', 'id': 'primary',
        'construction': primary_path, 'construction_sha256': digest(primary_path),
        'fixture_recipe': f'work/{ASSIGNMENT}/current-v2-probe-{number}-fixture-recipe.json',
        'measurement_contract': f'current-v2-probe-{number}-measurement-contract.json',
        'measurement_procedure': {'entrypoint': 'finalize.py', 'output_schema': 'c111294-saved-analysis-v1'},
        'candidate_risk': {'status': 'physical', 'reason': 'Original through body may overshoot its requested hold before the entering vehicle clears'},
        'candidates': [candidate],
        'offline': {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --candidate primary --output .runtime-work/c111294-selected-probe-{number}-primary-offline --python $PWD/.venv-cpu/bin/python',
                    'exit_code': 0, 'construction_sha256': digest(primary_path),
                    'log': primary_offline, 'log_sha256': digest(primary_offline)},
        'compatibility': compatibility(number, 'primary'),
        'negative': {'log': f'current-v2-probe-{number}-negative-analysis.log'},
        'saved_processing': evidence(f'current-v2-probe-{number}-saved-proof.json'),
        'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        'acquisition': {
            'through_body_pose': {'entrypoint': 'live_capture.py',
                                  'method': 'Original 20 Hz through actor transform, velocity, road/lane and body readback',
                                  'evidence': 'native_samples.jsonl, trace.jsonl, capture/evidence.jsonl and original four cameras'},
            'entrant_body_pose': {'entrypoint': 'live_capture.py',
                                  'method': 'Original 20 Hz entrant actor transform, velocity, road/lane and body readback',
                                  'evidence': 'native_samples.jsonl, capture/evidence.jsonl and authored-road.xodr'},
            'frame_join': {'entrypoint': 'live_capture.py',
                           'method': 'Synchronize both original actor observations to each Native tick and four camera frames',
                           'evidence': 'video_frames.jsonl, trace.jsonl and capture/native/frames.jsonl'},
        },
        'post_capture': {'command': f'python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$DECODER"',
                         'feedback_command': 'cat "$SAVED_OUTPUT"/v0001/feedback.json',
                         'recorded_only': True, 'test_exit_code': 0,
                         'test_log': f'current-v2-probe-{number}-saved-proof.json',
                         'test_log_sha256': digest(f'current-v2-probe-{number}-saved-proof.json')},
    }
    return entry


def main():
    path = HERE / 'execution-manifest.json'
    old = json.loads(path.read_text()) if path.is_file() else {'cases': []}
    old_entries = {entry['case_id']: entry for entry in old['cases']}
    data = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
            'runtime_manifest_sha256': RUNTIME,
            'status': 'selected_delivery_cpu_in_progress',
            'cases': [one(1), one(2)]}
    for entry in data['cases']:
        previous = old_entries.get(entry['case_id'], {})
        if previous.get('construction_sha256') == entry['construction_sha256']:
            for key in ('physical_preparation', 'delivery_acceptance', 'acquisition'):
                if key in previous:
                    entry[key] = previous[key]
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': digest('execution-manifest.json'),
                      'selected_cases': 2, 'fallbacks': 2,
                      'fallback_compatibility_bound': sum('compatibility' in c['candidates'][0] for c in data['cases'])}, sort_keys=True))


if __name__ == '__main__':
    main()
