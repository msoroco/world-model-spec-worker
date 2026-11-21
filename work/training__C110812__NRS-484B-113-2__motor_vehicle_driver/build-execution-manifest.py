"""Bind the exact selected CPU proofs to the formal delivery manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PREFIX = f'work/{ASSIGNMENT}/'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path, **extra):
    return {'receipt': str(path.relative_to(HERE)), 'sha256': sha(path), **extra}


def offline(entry, suffix, candidate):
    log = HERE / f'current-base-offline-{suffix}-{candidate}.log'
    selected = entry if candidate == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    return {'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest {PREFIX}execution-manifest.json '
                       f'--case {entry["case_id"]} --candidate {candidate} '
                       f'--output .runtime-work/c110812-formal-offline-{suffix}-{candidate}',
            'log': log.name, 'log_sha256': sha(log)}


def compatibility(suffix, candidate):
    if candidate == 'primary' and suffix == 'true':
        path = HERE / 'current-base-compatible-true-primary-receipt.json'
        log = HERE / 'current-base-compatible-true-primary-analysis.log'
        negative = HERE / 'current-base-compatible-true-primary-negative.log'
    else:
        path = HERE / f'current-base-{suffix}-{candidate}-compatibility-receipt.json'
        log = HERE / f'current-base-{suffix}-{candidate}-analysis.log'
        negative = HERE / f'current-base-{suffix}-{candidate}-negative.log'
    return reference(path, log=log.name, negative_log=negative.name)


def main():
    harness = read(HERE / 'current-base-proof-manifest.json')
    current = sha(HERE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json')
    if harness['runtime_manifest_sha256'] != current:
        raise ValueError('Selected proof harness binds another runtime')
    matrix_path = HERE / 'current-base-matrix-summary.json'
    if not matrix_path.is_file() or len(read(matrix_path).get('rows', [])) != 8:
        raise ValueError('All eight current-runtime compatibility and saved proofs must pass first')
    comparison = read(HERE / 'selected-comparison-proof.json')
    acceptance = read(HERE / 'selected-delivery-proof.json')
    entries = []
    for old in harness['cases']:
        entry = dict(old)
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        proof = next(x for x in acceptance['cases'] if x['case_id'] == entry['case_id'])
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['offline'] = offline(entry, suffix, 'primary')
        entry['compatibility'] = compatibility(suffix, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate['offline'] = offline(entry, suffix, ident)
            candidate['compatibility'] = compatibility(suffix, ident)
        bundle = read(HERE / entry['construction'])
        config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
        required = set(config['required_atoms']) | {
            channel['name'] for channel in bundle['recording_description']['channels']}
        entry['acquisition'] = {name: {'entrypoint': 'finalize.py',
            'method': 'derive from retained original Native sample, frame map, road geometry and synchronized source cameras',
            'evidence': 'native_samples.jsonl; video_frames.jsonl; road_geometry.json; four named source videos'}
            for name in sorted(required)}
        saved_log = HERE / f'current-base-saved-{suffix}-primary.log'
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest {PREFIX}execution-manifest.json '
                       f'--case {entry["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" '
                       '--library runtime/pipeline/library --validator "$DECODER"',
            'feedback_command': 'inspect "$OUTPUT/feedback.json" on failure',
            'test_log': saved_log.name, 'test_log_sha256': sha(saved_log), 'test_exit_code': 0}
        physical = HERE / proof['physical_receipt']
        entry['physical_preparation'] = reference(physical)
        script = HERE / 'audit-selected-delivery.py'
        command = f'.venv-cpu/bin/python {PREFIX}{script.name} --case {entry["case_id"]}'
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': command, 'test_exit_code': 0,
            'test_log': proof['positive_log'], 'test_log_sha256': proof['positive_sha256'],
            'negative_command': command + ' --remove-native-source',
            'negative_exit_code': 1, 'negative_expected_error': proof['negative_expected_error'],
            'negative_log': proof['negative_log'], 'negative_log_sha256': proof['negative_sha256'],
            'cpu_scope': 'synthetic source audit; actual pixels and physical completion unverified'}
        compare_script = HERE / 'audit-selected-comparison.py'
        positive = next(x for x in comparison['rows'] if x['label'] == 'positive')
        negative = next(x for x in comparison['rows'] if x['label'] == 'negative-drift')
        entry['comparison_audit'] = {
            'script': compare_script.name, 'script_sha256': sha(compare_script),
            'command': f'.venv-cpu/bin/python {PREFIX}{compare_script.name}',
            'test_log': positive['log'], 'test_log_sha256': positive['sha256'],
            'test_exit_code': positive['exit_code'],
            'negative_command': f'.venv-cpu/bin/python {PREFIX}{compare_script.name} --reject-comparison-drift',
            'negative_log': negative['log'], 'negative_log_sha256': negative['sha256'],
            'negative_exit_code': negative['exit_code'],
            'negative_expected_error': 'Comparison fixed condition changed: primary'}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': harness['runtime_manifest_sha256'],
                'status': 'selected_cpu_partial', 'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
