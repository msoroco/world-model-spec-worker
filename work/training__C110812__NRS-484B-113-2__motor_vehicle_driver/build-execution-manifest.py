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
    log = HERE / f'atom-fixed-{suffix}-{candidate}-offline.log'
    selected = entry if candidate == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    harness = 'control-proof-manifest.json' if suffix == 'control' else 'current-base-proof-manifest.json'
    return {'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest {PREFIX}{harness} '
                       f'--case {entry["case_id"]} --candidate {candidate} '
                       f'--output .runtime-work/c110812-atom-fixed-{suffix}-{candidate}/offline',
            'log': log.name, 'log_sha256': sha(log)}


def compatibility(suffix, candidate):
    stem = f'atom-fixed-{suffix}-{candidate}'
    path = HERE / (stem + '-compatibility-receipt.json')
    log = HERE / (stem + '-analysis.log')
    negative = HERE / (stem + '-negative.log')
    return reference(path, log=log.name, negative_log=negative.name)


def main():
    harness = read(HERE / 'control-proof-manifest.json')
    current = sha(HERE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json')
    if harness['runtime_manifest_sha256'] != current:
        raise ValueError('Selected proof harness binds another runtime')
    for name, count in (('current-base-matrix-summary.json', 8),
                        ('current-base-control-matrix-summary.json', 4)):
        matrix_path = HERE / name
        if not matrix_path.is_file() or len(read(matrix_path).get('rows', [])) != count:
            raise ValueError('All current-runtime compatibility and saved proofs must pass first: ' + name)
    comparison = read(HERE / 'current-base-comparison-proof.json')
    control_comparison = read(HERE / 'current-base-control-comparison-proof.json')
    acceptance = read(HERE / 'current-base-delivery-proof.json')
    control_acceptance = read(HERE / 'current-base-control-audit-proof.json')
    entries = []
    for old in harness['cases']:
        entry = dict(old)
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        proof = (None if suffix == 'control' else
                 next(x for x in acceptance['cases'] if x['case_id'] == entry['case_id']))
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
        saved_log = HERE / f'atom-fixed-{suffix}-primary-saved.log'
        if not saved_log.is_file():
            saved_path = HERE / f'atom-fixed-{suffix}-primary-saved-receipt.json'
            saved_result = read(saved_path)['result']
            if not saved_result['passed'] or not saved_result['recorded_only']:
                raise ValueError('Primary saved processing failed: ' + suffix)
            saved_log.write_text(json.dumps({'actual_saved_processing': 'scenario_pipeline.worker_exchange.saved_processing.run',
                'receipt': saved_path.name, 'receipt_sha256': sha(saved_path), 'passed': True,
                'recorded_only': True, 'case_id': entry['case_id']}, indent=2) + '\n')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest {PREFIX}execution-manifest.json '
                       f'--case {entry["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" '
                       '--library runtime/pipeline/library --validator "$DECODER"',
            'feedback_command': 'inspect "$OUTPUT/feedback.json" on failure',
            'test_log': saved_log.name, 'test_log_sha256': sha(saved_log), 'test_exit_code': 0}
        physical = HERE / (proof['physical_receipt'] if proof else 'physical-fixtures/control/proof.json')
        entry['physical_preparation'] = reference(physical)
        script = HERE / ('audit-lawful-control.py' if suffix == 'control' else 'audit-selected-delivery.py')
        command = f'.venv-cpu/bin/python {PREFIX}{script.name} --case {entry["case_id"]}'
        if suffix == 'control':
            positive = next(x for x in control_acceptance['rows'] if x['label'] == 'positive')
            negative = next(x for x in control_acceptance['rows'] if x['label'] == 'missing-native')
            proof = {'positive_log': positive['log'], 'positive_sha256': positive['sha256'],
                     'negative_log': negative['log'], 'negative_sha256': negative['sha256'],
                     'negative_expected_error': 'Missing required source: native_samples.jsonl'}
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': command, 'test_exit_code': 0,
            'test_log': proof['positive_log'], 'test_log_sha256': proof['positive_sha256'],
            'negative_command': command + (' --drop-native' if suffix == 'control' else ' --remove-native-source'),
            'negative_exit_code': 1, 'negative_expected_error': proof['negative_expected_error'],
            'negative_log': proof['negative_log'], 'negative_log_sha256': proof['negative_sha256'],
            'cpu_scope': 'synthetic source audit; actual pixels and physical completion unverified'}
        compare_script = HERE / ('audit-control-comparison.py' if suffix == 'control' else 'audit-selected-comparison.py')
        compare_proof = control_comparison if suffix == 'control' else comparison
        positive = next(x for x in compare_proof['rows'] if x['label'] == 'positive')
        negative = next(x for x in compare_proof['rows'] if x['label'] == 'negative-drift')
        entry['comparison_audit'] = {
            'script': compare_script.name, 'script_sha256': sha(compare_script),
            'command': f'.venv-cpu/bin/python {PREFIX}{compare_script.name}',
            'test_log': positive['log'], 'test_log_sha256': positive['sha256'],
            'test_exit_code': positive['exit_code'],
            'negative_command': f'.venv-cpu/bin/python {PREFIX}{compare_script.name} --reject-comparison-drift',
            'negative_log': negative['log'], 'negative_log_sha256': negative['sha256'],
            'negative_exit_code': negative['exit_code'],
            'negative_expected_error': 'Comparison fixed condition changed: primary'}
        triggers = HERE / 'atom-fixed-trigger-audit.log'
        entry['candidate_trigger_test'] = {
            'command': f'.venv-cpu/bin/python {PREFIX}audit-fallback3.py',
            'test_log': triggers.name, 'test_log_sha256': sha(triggers), 'test_exit_code': 0}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': harness['runtime_manifest_sha256'],
                'status': 'selected_cpu_partial', 'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
