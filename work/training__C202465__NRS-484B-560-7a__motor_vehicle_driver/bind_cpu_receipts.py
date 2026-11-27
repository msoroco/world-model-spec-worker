"""Bind exact CPU receipts to selected rail cases after all checks pass."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        for candidate in [entry, *entry['candidates']]:
            label = candidate['id']
            receipt = HERE / 'proofs' / suffix / ('public-' + label) / 'receipt.json'
            proof = json.loads(receipt.read_text())
            assert proof['passed'] and proof['case_id'] == case
            assert proof['construction_sha256'] == candidate['construction_sha256']
            prefix = f'proofs/{suffix}/public-{label}/'
            candidate['compatibility'] = {
                'receipt': prefix + 'receipt.json', 'sha256': digest(receipt),
                'log': prefix + 'analysis.log',
                'negative_log': prefix + 'negative.log'}
            offline = HERE / f'selected-{suffix}-{label}-offline.log'
            assert offline.is_file() and 'passed' in offline.read_text()
            candidate['offline'] = {
                'command': f'runtime.py offline --case {case} --candidate {label}',
                'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0, 'log': offline.name,
                'log_sha256': digest(offline)}
        entry['negative'] = {'log': f'proofs/{suffix}/public-primary/negative.log'}
        saved = HERE / 'proofs' / suffix / 'saved-processing.json'
        assert json.loads(saved.read_text())['passed']
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': f'inspect $OUTPUT/v0001/feedback.json for {case} on failure',
            'test_exit_code': 0, 'test_log': str(saved.relative_to(HERE)),
            'test_log_sha256': digest(saved)}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        required = set(config.get('required_atoms', [])) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        entry['acquisition'] = {name: {
            'entrypoint': 'finalize.py',
            'method': 'saved 600-frame original Native actor, rail geometry, vehicle extent, opposite-side space and four-camera frame join',
            'evidence': 'actors.jsonl; rail-actors.jsonl; rail-context.json; rail-review sources; video_frames.jsonl; four source videos'}
            for name in sorted(required)}
        physical = HERE / 'proofs' / 'physical' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': digest(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['delivery_readiness'] = 'cpu_prepared_original_rail_source_pending'
    manifest['status'] = 'cpu_prepared_original_rail_source_pending'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(digest(path))


if __name__ == '__main__':
    main()
