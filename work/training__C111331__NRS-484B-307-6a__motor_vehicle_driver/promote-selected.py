"""Promote the authored yellow/red pair to current-input CPU delivery packages."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    source_sha = sha(ROOT / 'inputs' / AID / 'assignment.json')
    draft = read(HERE / 'draft-execution-manifest.json')
    plan = read(HERE / 'case-plan.json')
    if {c['case_id'] for c in draft['cases']} != {c['case_id'] for c in plan['cases']}:
        raise ValueError('Selected case scope differs from plan')
    plan['evidence_review'] = {
        'method': 'Reviewed frozen assignment, witness, and local evidence inventory; no evidence.json or source-hashed equivalence receipt supplied.',
        'accepted_recordings': [], 'demonstrated_facts': [],
        'membership_only': plan['existing_evidence'],
        'limitations': ['Set membership does not establish entry phase, Native provenance, original pixels, or statutory coverage.'],
        'gaps': [{'case_id': c['case_id'], 'requirement': 'observed original vehicle-body entry joined to signal exhibition and four source cameras'} for c in plan['cases']]}
    mapping = {
        'dev.traffic_signal': ['observed_signal_state', 'signal_camera_frame_join'],
        'dev.governs': ['observed_signal_state', 'native_body_pose'],
        'st.lane_enters': ['native_body_pose'],
        'kin.time': ['native_body_pose', 'observed_signal_state', 'signal_camera_frame_join'],
        'drv.entering_intersection': ['native_body_pose'],
        'st.intersection': ['native_body_pose'],
        'drv.crossing_line': ['native_body_pose'],
        'kin.speed': ['native_body_pose'],
        'drv.stopping_distance': ['native_body_pose'],
    }
    for term, channels in mapping.items():
        plan['source_observation_mapping'][term] = {
            'evidence': 'Retained original Native tick data and synchronized source-camera join are required; physical values remain unverified.',
            'channels': channels,
            'source_refs': ['native_samples.jsonl', 'video_frames.jsonl', 'reference_corner.mkv']}
    plan['observations'] = [
        {'name': 'native_body_pose', 'unit': 'structured', 'mandatory': True,
         'purpose': 'Observed vehicle body, velocity and intersection entry by Native frame'},
        {'name': 'observed_signal_state', 'unit': 'structured', 'mandatory': True,
         'purpose': 'Observed yellow and red exhibition on the governing signal'},
        {'name': 'signal_camera_frame_join', 'unit': 'structured', 'mandatory': True,
         'purpose': 'Original signal pixels joined to Native frames'}]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 24,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': name, 'subject': subject, 'interval': 'all 480 frames'}
                     for name, subject in (
                         ('overview', 'full intersection and vehicle'),
                         ('approach', 'vehicle approach and governing signal'),
                         ('reference_corner', 'governing signal head and entry boundary'),
                         ('driver_reference', 'driver vehicle and forward context'))],
        'original_visibility_verified': False}
    write(HERE / 'case-plan.json', plan)

    manifest = {k: v for k, v in draft.items() if k != 'source_branch'}
    manifest['format'] = 'worker-execution-manifest'
    manifest['status'] = 'selected_cpu_proof_in_progress'
    manifest['selection_review'] = {
        'law_input_sha256': source_sha, 'case_plan_sha256': sha(HERE / 'case-plan.json'),
        'draft_proposal_sha256': sha(HERE / 'proposals/cases.json'),
        'accepted_memberships': 0,
        'unresolved': ['original Native vehicle-body entry and signal phase', 'four-view original pixels'],
        'scope': 'Two same-cell yellow-before-red and red-at-entry controlled delivery cases; no original outcome claimed.'}
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(AID + '__')
        entry['kind'] = 'delivery'
        entry['preparation_status'] = 'selected; current offline, compatibility and saved processing pending'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['candidate_risk']['reason'] = 'Native signal head, vehicle entry and four-camera pixels must agree with the authored timing; physical outcome unverified.'
        for candidate in [entry, *entry['candidates']]:
            name = candidate['id']
            bundle = read(HERE / candidate['construction'])
            config_file = next(f for f in bundle['files'] if f['path'] == 'config.json')
            config = json.loads(config_file['content'])
            config['assignment_source_sha256'] = source_sha
            config['status'] = 'selected_cpu_delivery_request'
            config_file['content'] = json.dumps(config, indent=2) + '\n'
            finalizer_file = next(f for f in bundle['files'] if f['path'] == 'finalize.py')
            finalizer_file['content'] = (HERE / 'native' / 'finalize.py').read_text()
            bundle['status'] = 'selected_cpu_delivery_request'
            target = HERE / 'selected-candidates' / suffix / name / 'construction.json'
            write(target, bundle)
            candidate['construction'] = str(target.relative_to(HERE))
            candidate['construction_sha256'] = sha(target)
        entry['delivery_acceptance'] = {'case_id': entry['case_id'], 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion']}
    write(HERE / 'execution-manifest.json', manifest)
    first = read(HERE / manifest['cases'][0]['construction'])
    for item in first['files']:
        if item['path'].startswith('tests/'):
            continue
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    root_config = read(HERE / 'config.json')
    root_config['supported_case_ids'] = sorted(c['case_id'] for c in manifest['cases'])
    root_config['cameras'] = [{'name': name, 'width': width, 'height': height,
                               'fps': 20, 'pose_strategy': strategy}
        for name, width, height, strategy in (
            ('overview', 1920, 1080, 'fixed overhead intersection'),
            ('approach', 1280, 720, 'fixed south approach'),
            ('reference_corner', 1280, 720, 'fixed governing signal head'),
            ('driver_reference', 1280, 720, 'attached to ego vehicle'))]
    write(HERE / 'config.json', root_config)
    root_construction = dict(first)
    root_construction['format'] = 'c111331-portable-two-case-catalog-v1'
    root_construction['status'] = 'selected_cpu_delivery_request'
    root_construction['files'] = [f for f in first['files'] if f['path'] != 'config.json'] + [
        {'path': 'config.json', 'content': (HERE / 'config.json').read_text()}]
    write(HERE / 'construction.json', root_construction)
    print(json.dumps({'cases': 2, 'candidates': 8, 'source_sha256': source_sha,
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
