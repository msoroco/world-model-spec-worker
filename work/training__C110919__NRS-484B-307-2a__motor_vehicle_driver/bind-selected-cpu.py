"""Bind tested current-runtime CPU receipts; never set package readiness."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/owner194-next'

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path: Path) -> dict:
    return json.loads(path.read_text())

def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

manifest_path = HERE / 'execution-manifest.json'
manifest = read(manifest_path)
for index, entry in enumerate(manifest['cases'], 1):
    case = entry['case_id']
    for candidate in [dict(id='primary'), *entry['candidates']]:
        ident = candidate['id']
        target = entry if ident == 'primary' else next(x for x in entry['candidates']
                                                     if x['id'] == ident)
        construction_sha = target['construction_sha256']
        offline_log = HERE / f'rebuilt-{index}-{ident}-offline.log'
        offline_command = (f'.venv-cpu/bin/python runtime.py offline --manifest '
            f'work/{HERE.name}/execution-manifest.json --case {case} '
            f'--candidate {ident} --output .runtime-work/owner194-next/rebuilt-{index}-{ident}-offline')
        assert read(offline_log)['offline_passed'] is True
        target['offline'] = {'command': offline_command, 'exit_code': 0,
            'construction_sha256': construction_sha, 'log': offline_log.name,
            'log_sha256': sha(offline_log)}
        compat_log = HERE / f'rebuilt-{index}-{ident}-compat-v2.log'
        compat = read(compat_log)
        assert compat['passed'] is True and compat['construction_sha256'] == construction_sha
        assert compat['case_id'] == case and compat['candidate_id'] == ident
        receipt = HERE / f'selected-{index}-{ident}-compatibility.json'
        write(receipt, compat)
        source = SCRATCH / f'rebuilt-{index}-{ident}-compat-v2'
        analysis = HERE / f'selected-{index}-{ident}-analysis.log'
        negative = HERE / f'selected-{index}-{ident}-negative.log'
        shutil.copyfile(source / 'compatibility-analysis.log', analysis)
        shutil.copyfile(source / 'negative-analysis.log', negative)
        assert sha(analysis) == compat['log_sha256']
        assert sha(negative) == compat['negative_log_sha256']
        target['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
            'log': analysis.name, 'negative_log': negative.name}
        if ident == 'primary':
            entry['negative'] = {'log': negative.name, 'sha256': sha(negative)}
        saved_log = HERE / f'rebuilt-{index}-{ident}-saved.log'
        saved = read(saved_log)
        assert saved['case_id'] == case and saved['originals_preserved'] is True
        assert saved['physical_acceptance_claimed'] is False
        saved_receipt = HERE / f'selected-{index}-{ident}-saved.json'
        write(saved_receipt, saved)
        result = HERE / f'selected-{index}-{ident}-result.json'
        shutil.copyfile(source / 'result.json', result)
        target['saved_processing'] = {'receipt': saved_receipt.name,
            'sha256': sha(saved_receipt), 'result': result.name,
            'result_sha256': sha(result), 'recorded_only': True}
    directory = HERE / f'physical-fixtures/controlled_{index}'
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = directory / f'{kind}.json'
        log = directory / f'{kind}.log'
        assert read(result)['provenance_kind'] == 'synthetic_fixture'
        assert 'cpu_branch_passed' in log.read_text()
        fixtures.append({'kind': kind,
            'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-cpu.py '
                       f'--index {index} --kind {kind} --output '
                       f'work/{HERE.name}/physical-fixtures/controlled_{index}/{kind}.json',
            'exit_code': 0, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'result': str(result.relative_to(HERE)),
            'result_sha256': sha(result)})
    lifecycle_result = directory / 'lifecycle.json'
    lifecycle_log = directory / 'lifecycle.log'
    lifecycle = {'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-cpu.py '
                           f'--index {index} --kind lifecycle --output '
                           f'work/{HERE.name}/physical-fixtures/controlled_{index}/lifecycle.json',
        'events': read(lifecycle_result)['events'], 'exit_code': 0,
        'log': str(lifecycle_log.relative_to(HERE)),
        'log_sha256': sha(lifecycle_log),
        'result': str(lifecycle_result.relative_to(HERE)),
        'result_sha256': sha(lifecycle_result)}
    proof = {'format': 'worker-right-turn-physical-cpu-v1', 'case_id': case,
        'construction_sha256': entry['construction_sha256'],
        'script_sha256': sha(HERE / 'prove-physical-cpu.py'),
        'fixtures': fixtures, 'lifecycle': lifecycle,
        'scope': 'source-shaped synthetic physical outcome and ownership order only',
        'physical_or_legal_acceptance': False}
    path = directory / 'proof.json'
    write(path, proof)
    entry['physical_preparation'] = {'receipt': str(path.relative_to(HERE)),
                                     'sha256': sha(path)}
    positive = HERE / f'selected-{index}-delivery-positive.log'
    negative = HERE / f'selected-{index}-delivery-negative.log'
    assert read(positive)['mode'] == 'diagnostic'
    assert 'Missing source: native_samples.jsonl' in negative.read_text()
    script = HERE / 'delivery_audit.py'
    base = (f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py '
            f'--case {case} --attempt '
            f'.runtime-work/owner194-next/rebuilt-{index}-primary-compat-v2 '
            f'--mode diagnostic')
    entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': script.name, 'script_sha256': sha(script),
        'command': base, 'test_exit_code': 0,
        'test_log': positive.name, 'test_log_sha256': sha(positive),
        'negative_command': base + ' --exclude-source native_samples.jsonl',
        'negative_exit_code': 1,
        'negative_expected_error': 'Missing source: native_samples.jsonl',
        'negative_log': negative.name, 'negative_log_sha256': sha(negative),
        'diagnostic_scope': 'synthetic source shape only; original pixel review remains pending'}
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'}
    config = read(HERE / f'draft-candidates/controlled_{index}/primary/construction.json')
    config = json.loads(next(f['content'] for f in config['files'] if f['path'] == 'config.json'))
    acquired = set(config['required_atoms']) | {
        item['name'] for item in config['recording_description']['channels']}
    entry['acquisition'] = {name: {'entrypoint': 'runner.py' if name in
        ('st.intersection', 'kin.position', 'native_body_pose_control', 'camera_frame_join')
        else 'finalize.py', 'method': 'source-hashed Native/map/frame join',
        'evidence': 'native_samples.jsonl, road_geometry.json and video_frames.jsonl; '
                    'physical interpretation requires original Native and pixel review'}
        for name in sorted(acquired)}
    entry['recording_description'] = read(HERE / f'draft-candidates/controlled_{index}/primary/construction.json')['recording_description']
manifest['status'] = 'selected_cpu_proofs_bound_physical_unverified'
write(manifest_path, manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'cases': len(manifest['cases']),
                  'fallbacks': sum(len(c['candidates']) for c in manifest['cases'])}))
