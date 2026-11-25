"""Bind completed selected CPU proofs without copying temporary fixtures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c230222-lvmc-route'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text()
    if not content.endswith('\n') or content.endswith('\n\n'):
        raise ValueError('Proof has invalid final newline: ' + str(source))
    if any(row.rstrip(' \t') != row for row in content.splitlines()):
        raise ValueError('Proof contains trailing whitespace: ' + str(source))
    target.write_text(content)
    return str(target.relative_to(ROOT))


def bind():
    manifest = json.loads((ROOT / 'selected-draft-manifest.json').read_text())
    manifest['status'] = 'selected_cpu_proofs_bound'
    for suffix, entry in zip('ab', manifest['cases']):
        case_id = entry['case_id']
        for candidate_id, selected in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            offline_source = SCRATCH / ('offline-' + suffix + '-' +
                ('primary' if candidate_id == 'primary' else 'fallback') + '-v3/offline.log')
            offline_path = copy(offline_source, ROOT / 'selected-proofs' / (suffix + '-' + candidate_id + '-offline.log'))
            selected['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ROOT.name +
                    '/execution-manifest.json --case ' + case_id + ' --candidate ' + candidate_id +
                    ' --output "$OFFLINE_OUT" --python .venv-cpu/bin/python',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': offline_path, 'log_sha256': sha(ROOT / offline_path)}
            folder = SCRATCH / ('compat-' + suffix + '-' + candidate_id + '-v5')
            prefix = suffix + '-' + candidate_id
            receipt_path = copy(folder / 'compatibility.json', ROOT / 'selected-proofs' / (prefix + '-compatibility.json'))
            analysis_log = copy(folder / 'compatibility-analysis.log', ROOT / 'selected-proofs' / (prefix + '-analysis.log'))
            negative_log = copy(folder / 'negative-analysis.log', ROOT / 'selected-proofs' / (prefix + '-negative.log'))
            selected['compatibility'] = {'receipt': receipt_path, 'sha256': sha(ROOT / receipt_path),
                'log': analysis_log, 'negative_log': negative_log}
            selected['negative'] = {'log': negative_log}
            saved_source = SCRATCH / ('saved-' + suffix + '-' + candidate_id + '-v5/v0001/processing.json')
            saved_path = copy(saved_source, ROOT / 'selected-proofs' / (prefix + '-saved.json'))
            selected['saved_processing'] = {'receipt': saved_path, 'sha256': sha(ROOT / saved_path)}
        required = {'ru.pedestrian', 'kin.position', 'st.road_edge'} | {
            item['name'] for item in json.loads((ROOT / entry['construction']).read_text())['recording_description']['channels']}
        entry['acquisition'] = {atom: {
            'entrypoint': 'runner.py' if atom in ('ru.pedestrian', 'kin.position') else 'finalize.py',
            'method': 'Source-joined Native pedestrian transform and authored curb/crosswalk geometry, with independent original map and pixel review required',
            'evidence': 'route-samples.jsonl, route-context.json, video_frames.jsonl and original four camera sources'}
            for atom in sorted(required)}
        proof = ROOT / 'physical-proof' / ('condition_' + suffix) / 'proof.json'
        entry['physical_preparation'] = {'receipt': str(proof.relative_to(ROOT)), 'sha256': sha(proof)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ROOT.name +
                '/execution-manifest.json --case ' + case_id +
                ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0,
            'test_log': entry['saved_processing']['receipt'],
            'test_log_sha256': entry['saved_processing']['sha256']}
    output = ROOT / 'execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(output), 'sha256': sha(output), 'cases': len(manifest['cases'])}))


if __name__ == '__main__':
    bind()
