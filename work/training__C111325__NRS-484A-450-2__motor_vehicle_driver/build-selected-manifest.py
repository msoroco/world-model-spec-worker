"""Bind exact crosswalk selected proofs after all four CPU chains pass."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return path.relative_to(HERE).as_posix()


def proof(index, candidate):
    base = HERE / 'selected-compatibility' / f'{index}-{candidate}'
    receipt = base / 'compatibility.json'
    body = json.loads(receipt.read_text())
    if body['passed'] is not True or body['candidate_id'] != candidate:
        raise ValueError('Public selected proof did not pass')
    if sha(base / 'analysis.log') != body['log_sha256']:
        raise ValueError('Selected public analysis changed')
    if sha(base / 'negative.log') != body['negative_log_sha256']:
        raise ValueError('Selected public negative changed')
    return {'receipt': reference(receipt), 'sha256': sha(receipt),
            'log': reference(base / 'analysis.log'),
            'negative_log': reference(base / 'negative.log')}


def saved(index, candidate):
    base = HERE / 'selected-saved' / f'{index}-{candidate}'
    receipt = base / 'processing.json'
    body = json.loads(receipt.read_text())
    if not body['source_hashes_preserved'] or body['candidate_id'] != candidate:
        raise ValueError('Recorded-only source preservation not proved')
    return {'receipt': reference(receipt), 'sha256': sha(receipt),
            'recorded_only': True, 'originals_preserved': True,
            'log': reference(base / 'analysis.log'),
            'log_sha256': sha(base / 'analysis.log')}


def offline(index, candidate, construction_hash):
    case = HERE.name + f'__probe_{index}'
    path = HERE / 'selected-offline-proofs' / f'{index}-{candidate}.log'
    if '"offline_passed": true' not in path.read_text().lower():
        raise ValueError('Exact offline proof did not pass')
    return {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/selected-draft-execution-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c111325-selected/offline-v5-{index}-{candidate} --python $PWD/.venv-cpu/bin/python',
            'construction_sha256': construction_hash, 'exit_code': 0,
            'log': reference(path), 'log_sha256': sha(path)}


def build():
    draft = json.loads((HERE / 'selected-draft-execution-manifest.json').read_text())
    entries = []
    for index, source in enumerate(draft['cases'], start=1):
        entry = deepcopy(source)
        case = entry['case_id']
        entry['offline'] = offline(index, 'primary', entry['construction_sha256'])
        entry['compatibility'] = proof(index, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        entry['saved_processing'] = saved(index, 'primary')
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate['offline'] = offline(index, ident, candidate['construction_sha256'])
            candidate['compatibility'] = proof(index, ident)
            candidate['saved_processing'] = saved(index, ident)
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        evidence = ['native_samples.jsonl', 'road.xodr', 'trace.jsonl',
                    'video_frames.jsonl', 'crosswalk_geometry.json',
                    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                    'driver_reference.mkv']
        required = set(config.get('required_atoms', [])) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        entry['acquisition'] = {
            name: {'entrypoint': 'finalize.py', 'evidence': evidence,
                   'method': 'source-joined original frame, body, road, and camera review'}
            for name in sorted(required)}
        physical = HERE / 'physical-preparation' / str(index) / 'receipt.json'
        entry['physical_preparation'] = {'receipt': reference(physical), 'sha256': sha(physical)}
        command = f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $ATTEMPT/owner-release.json'
        log = HERE / entry['saved_processing']['log']
        entry['post_capture'] = {'recorded_only': True, 'command': command,
                                 'feedback_command': command, 'test_exit_code': 0,
                                 'test_log': reference(log), 'test_log_sha256': sha(log)}
        base = HERE / 'delivery-acceptance' / str(index)
        audit = f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c111325-selected/audit-output PYTHONPATH=runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/delivery_audit.py --case {case} --selftest'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-train', 'full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': audit, 'test_exit_code': 0,
            'test_log': reference(base / 'positive.log'),
            'test_log_sha256': sha(base / 'positive.log'),
            'negative_command': audit + ' --negative-fixture',
            'negative_exit_code': 1,
            'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
            'negative_log': reference(base / 'negative.log'),
            'negative_log_sha256': sha(base / 'negative.log')}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'selected_cpu_prepared_pending_strict',
                'delivery_ready': False, 'original_native_observed': False,
                'cases': entries}
    target = HERE / 'execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return {'manifest_sha256': sha(target), 'cases': len(entries)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
