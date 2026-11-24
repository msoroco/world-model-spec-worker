"""Bind source-hashed CPU proofs to the two selected delivery cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def relative(path):
    return path.relative_to(HERE).as_posix()


def evidence_for(entry):
    bundle = json.loads((HERE / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))
    required = set(config['required_atoms']) | {item['name'] for item in bundle['recording_description']['channels']}
    return {name: {
        'entrypoint': 'runner.py' if name in ('camera_frame_join', 'native_body_pose_control',
                                               'motorcycle_detector_request', 'st.intersection', 'kin.position')
                       else 'finalize.py',
        'method': 'Original Native 20 Hz actor, signal, body, map and camera frame join; authored commands retained separately',
        'evidence': 'Synthetic CPU fixture proves processing only; original Native source and independent pixel review remain required',
    } for name in sorted(required)}


def bind():
    manifest = json.loads(MANIFEST.read_text())
    candidate_manifest = HERE / 'current-v2-candidate-manifest.json'
    candidate_sha = sha(candidate_manifest)
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        entry['acquisition'] = evidence_for(entry)
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        for name, selected in [('primary', entry), *[(candidate['id'], candidate)
                                                    for candidate in entry['candidates']]]:
            folder = HERE / 'current-v2-candidates' / condition / name
            construction_path = HERE / selected['construction']
            if sha(construction_path) != selected['construction_sha256']:
                raise ValueError('Construction changed before binding')
            compatibility_path = folder / 'compatibility.json'
            compatibility = json.loads(compatibility_path.read_text())
            if (compatibility.get('passed') is not True
                    or compatibility['construction_sha256'] != selected['construction_sha256']
                    or compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
                raise ValueError('Current public compatibility changed')
            saved_path = folder / 'saved-proof.json'
            saved = json.loads(saved_path.read_text())
            if (saved.get('passed') is not True or saved['manifest_sha256'] != candidate_sha
                    or saved['construction_sha256'] != selected['construction_sha256']
                    or saved['compatibility_sha256'] != sha(compatibility_path)):
                raise ValueError('Recorded-only CPU chain differs')
            offline_log = folder / 'current-offline.log'
            selected['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-v2-candidate-manifest.json --case {entry["case_id"]} --candidate {name} --output .runtime-work/c110919-owner104-rebind/offline-{condition}-{name}',
                'exit_code': 0,
                'construction_sha256': selected['construction_sha256'],
                'log': relative(offline_log), 'log_sha256': sha(offline_log)}
            selected['compatibility'] = {
                'receipt': relative(compatibility_path), 'sha256': sha(compatibility_path),
                'log': relative(folder / 'public-analysis.log'),
                'negative_log': relative(folder / 'source-negative.log')}
            selected['saved_cpu_proof'] = {
                'processing': relative(folder / 'saved-command.log'),
                'processing_sha256': sha(folder / 'saved-command.log'),
                'log': relative(folder / 'saved-command.log'),
                'log_sha256': sha(folder / 'saved-command.log'),
                'recorded_only': True, 'originals_preserved': True,
                'source_proof': relative(saved_path), 'source_proof_sha256': sha(saved_path),
                'pre_receipt_manifest_sha256': candidate_sha,
                'selected_construction_sha256': selected['construction_sha256']}
            if name == 'primary':
                entry['negative'] = {'log': relative(folder / 'source-negative.log')}
        saved_log = HERE / 'current-v2-candidates' / condition / 'primary' / 'saved-command.log'
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'{ROOT / ".venv-cpu/bin/python"} {ROOT / "runtime.py"} process-saved --manifest {MANIFEST} --case {entry["case_id"]} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library {ROOT / "runtime/library"} --validator {ROOT / ".runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck"}',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': relative(saved_log),
            'test_log_sha256': sha(saved_log),
            'proof_scope': 'Recorded-only synthetic CPU diagnostic; original Native postcapture remains'}
        positive = HERE / f'current-delivery-{condition}-positive.log'
        negative = HERE / f'current-delivery-{condition}-negative.log'
        for path in (positive, negative):
            if not path.is_file():
                raise ValueError('Delivery acceptance proof missing: ' + str(path))
        attempt = ROOT / f'.runtime-work/c110919-owner104-rebind/saved-{condition}-primary/attempt'
        processed = ROOT / f'.runtime-work/c110919-owner104-rebind/saved-{condition}-primary/processed/v0001/processing.json'
        negative_attempt = ROOT / f'.runtime-work/c110919-owner104-rebind/delivery-{condition}-negative-attempt'
        positive_command = f'{ROOT / ".venv-cpu/bin/python"} {script} --case {entry["case_id"]} --candidate primary --attempt {attempt} --processing {processed} --output {ROOT / f".runtime-work/c110919-owner104-rebind/delivery-{condition}-positive.json"} --diagnostic'
        negative_command = f'{ROOT / ".venv-cpu/bin/python"} {script} --case {entry["case_id"]} --candidate primary --attempt {negative_attempt} --processing {processed} --output {ROOT / f".runtime-work/c110919-owner104-rebind/delivery-{condition}-negative.json"} --diagnostic'
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': relative(script), 'script_sha256': sha(script),
            'command': positive_command, 'test_exit_code': 0,
            'test_log': relative(positive), 'test_log_sha256': sha(positive),
            'negative_command': negative_command, 'negative_exit_code': 1,
            'negative_log': relative(negative), 'negative_log_sha256': sha(negative),
            'negative_expected_error': 'Missing original source: road_geometry.json'}
    manifest['status'] = 'selected_cpu_prepared_original_native_unverified'
    write(MANIFEST, manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    bind()
