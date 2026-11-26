"""Bind tested exact-case CPU artifacts into the selected handoff."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def ref(relative):
    path = ROOT / relative
    return {'receipt': relative, 'sha256': sha(path)}


def main():
    draft = json.loads((ROOT / 'selected-draft-manifest.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'selected_cpu_proofs_passed', 'original_native_observed': False,
                'delivery_ready': False, 'cases': []}
    root_construction = json.loads((ROOT / draft['cases'][0]['construction']).read_text())
    write(ROOT / 'construction.json', root_construction)
    for file in root_construction['files']:
        destination = ROOT / file['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(file['content'])
    script = 'delivery_audit.py'
    for draft_entry in draft['cases']:
        case = draft_entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        short = suffix.replace('_', '')
        proof = f'selected-proofs/{suffix}'
        physical = f'selected-physical/{suffix}'
        fallback = f'selected-proofs/{suffix}-fallback1'
        fallback_receipt = ROOT / fallback / 'compatibility.json'
        if not fallback_receipt.is_file():
            raise ValueError('Missing tested fallback compatibility for ' + case)
        primary = json.loads((ROOT / draft_entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in primary['files'] if f['path'] == 'config.json'))
        offline = f'probe-{suffix[-2:]}-offline-current.log'
        fallback_log = f'{physical}/fallback-offline.log'
        fallback_entry = draft_entry['candidates'][0]
        fallback_entry['offline'] = {
            'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{AID}/selected-draft-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c190631-offline-{suffix}-fallback1-v1 --python $PWD/.venv-cpu/bin/python',
            'construction_sha256': fallback_entry['construction_sha256'], 'exit_code': 0,
            'log': fallback_log, 'log_sha256': sha(ROOT / fallback_log)}
        fallback_entry['compatibility'] = {
            **ref(f'{fallback}/compatibility.json'),
            'log': f'{fallback}/public-analysis.log',
            'negative_log': f'{fallback}/negative-analysis.log'}
        acquisition = {name: {'entrypoint': 'runner.py',
            'method': 'original Native walker pose and footprint joined to surveyed sidewalk and roadway, frame map and four synchronized source cameras',
            'evidence': ['pedestrian-poses.jsonl', 'surface-geometry.json', 'video_frames.jsonl',
                         'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']}
            for name in {item['name'] for item in primary['recording_description']['channels']} |
                        set(config.get('required_atoms', []))}
        positive = f'{physical}/delivery-positive.log'
        negative = f'{physical}/delivery-negative.log'
        audit_command = f'PYTHONPATH=$PWD/work/{AID} .venv-cpu/bin/python -B work/{AID}/{script} --case {case} --attempt $ATTEMPT'
        entry = {'case_id': case, 'kind': 'delivery',
            'construction': draft_entry['construction'],
            'construction_sha256': draft_entry['construction_sha256'],
            'measurement_contract': draft_entry['measurement_contract'],
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'fixture_recipe': draft_entry['fixture_recipe'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original walker may fail to spawn at x=-30; source-measured spawn failure selects a same-surface x=-28 alternative.'},
            'candidates': [fallback_entry],
            'offline': {'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{AID}/draft-roadway-manifest.json --case {case} --output .runtime-work/c190631-offline-updated-{suffix} --python $PWD/.venv-cpu/bin/python',
                        'construction_sha256': draft_entry['construction_sha256'],
                        'exit_code': 0, 'log': offline, 'log_sha256': sha(ROOT / offline)},
            'compatibility': {**ref(f'{proof}/compatibility.json'),
                              'log': f'{proof}/public-analysis.log',
                              'negative_log': f'{proof}/negative-analysis.log'},
            'negative': {'log': f'{proof}/negative-analysis.log'},
            'saved_processing': {**ref(f'{proof}/processing.json'),
                                 'recorded_only': True, 'originals_preserved': True,
                                 'log': f'{proof}/saved.log',
                                 'log_sha256': sha(ROOT / proof / 'saved.log')},
            'post_capture': {'recorded_only': True,
                'command': f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $ATTEMPT/owner-release.json',
                'feedback_command': f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $ATTEMPT/owner-release.json',
                'test_exit_code': 0, 'test_log': f'{proof}/saved.log',
                'test_log_sha256': sha(ROOT / proof / 'saved.log')},
            'physical_preparation': ref(f'{physical}/physical-preparation.json'),
            'acquisition': acquisition,
            'delivery_acceptance': {'case_id': case, 'sets': ['full-train'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': script, 'script_sha256': sha(ROOT / script),
                'command': audit_command + ' --diagnostic',
                'test_exit_code': 0, 'test_log': positive,
                'test_log_sha256': sha(ROOT / positive),
                'negative_command': audit_command,
                'negative_exit_code': 1,
                'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
                'negative_log': negative,
                'negative_log_sha256': sha(ROOT / negative)}}
        manifest['cases'].append(entry)
    write(ROOT / 'execution-manifest.json', manifest)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for planned in plan['cases']:
        planned['target_type'] = 'judgment_sweep'
        planned['selection_status'] = 'selected_cpu_proofs_passed_physical_unverified'
    plan['comparisons'][0]['proof_status'] = 'independent_synthetic_source_audit_positive_and_original_source_negative_passed'
    write(ROOT / 'case-plan.json', plan)
    print('assembled exact selected manifest')


if __name__ == '__main__':
    main()
