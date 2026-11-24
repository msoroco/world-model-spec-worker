"""Bind the measured six-chain CPU matrix to two exact selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MATRIX = HERE / 'current-v2-matrix'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    proof = json.loads((HERE / 'current-v2-six-chain-proof.json').read_text())
    assert proof['passed'] and len(proof['rows']) == 6
    runtime_sha = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': runtime_sha,
                'status': 'selected_cpu_preparation_pending_independent_audits', 'cases': []}
    for suffix in ('probe_a', 'probe_b'):
        source = json.loads((HERE / f'current-v2-{suffix}-candidate-manifest.json').read_text())
        entry = source['cases'][0]
        assert source['runtime_manifest_sha256'] == runtime_sha
        case_id = entry['case_id']
        entry['kind'] = 'delivery'
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Original route cross-track error and final braking margin are unverified; each has a separately triggered engineering alternative.'}
        for candidate_id, selected in [('primary', entry)] + [(c['id'], c) for c in entry['candidates']]:
            row = next(r for r in proof['rows'] if r['case_id'] == case_id and r['candidate_id'] == candidate_id)
            assert row['construction_sha256'] == selected['construction_sha256']
            base = f'current-v2-matrix/{suffix}/{candidate_id}'
            selected['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-v2-{suffix}-candidate-manifest.json --case {case_id} --candidate {candidate_id} --output .runtime-work/c110454-450-fallbacks/offline3-{suffix}-{candidate_id}',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': f'{base}/offline.log', 'log_sha256': row['offline_log_sha256']}
            selected['compatibility'] = {'receipt': f'{base}/compatibility.json',
                'sha256': row['compatibility_sha256'], 'log': f'{base}/public-analysis.log',
                'negative_log': f'{base}/negative-analysis.log'}
            selected['saved_cpu_proof'] = {'processing': f'{base}/processing.json',
                'processing_sha256': row['saved_processing_sha256'],
                'log': f'{base}/processing.json', 'log_sha256': row['saved_processing_sha256'],
                'recorded_only': True, 'originals_preserved': True,
                'selected_construction_sha256': selected['construction_sha256']}
        config = json.loads(next(x['content'] for x in json.loads((HERE / entry['construction']).read_text())['files']
                                 if x['path'] == 'config.json'))
        channels = {x['name'] for x in json.loads((HERE / entry['construction']).read_text())['recording_description']['channels']}
        required = channels | set(config['required_atoms'])
        entry['acquisition'] = {name: {'entrypoint': 'runner.py' if name in ('native_body_pose_control', 'camera_frame_join') else 'finalize.py',
            'method': 'Source-hashed original Native body, map, controller and synchronized frame join; synthetic CPU proof checks processing only',
            'evidence': 'Original Native acquisition and source-qualified exception circumstances require local review'}
            for name in sorted(required)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['negative'] = {'log': f'current-v2-matrix/{suffix}/primary/negative-analysis.log'}
        entry['post_capture'] = {'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case_id} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$LEAN_VALIDATOR"',
            'feedback_command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case_id} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$LEAN_VALIDATOR"',
            'test_exit_code': 0,
            'test_log': f'current-v2-matrix/{suffix}/primary/processing.json',
            'test_log_sha256': next(r for r in proof['rows'] if r['case_id']==case_id and r['candidate_id']=='primary')['saved_processing_sha256'],
            'proof_scope': 'Recorded-only synthetic CPU source and processing; physical result unverified'}
        manifest['cases'].append(entry)
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
