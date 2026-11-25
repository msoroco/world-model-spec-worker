"""Bind completed exact NRS island-side CPU proofs into the delivery package."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'island, ego body and rotary roadway', 'interval': 'full 30 s'},
            {'view': 'approach', 'subject': 'island approach and entrance', 'interval': 'full 30 s'},
            {'view': 'reference_corner', 'subject': 'island and ego body on both passage sides', 'interval': 'full 30 s'},
            {'view': 'driver_reference', 'subject': 'driver view of island and rotary lane', 'interval': 'full 30 s'}]}
    plan['observations'] = [
        {'name': 'kin.position', 'unit': 'm', 'mandatory': True,
         'purpose': 'Original Native body center and vertices on every passage frame'},
        {'name': 'kin.heading', 'unit': 'deg', 'mandatory': True,
         'purpose': 'Original Native direction and island-side bearing'},
        {'name': 'island_side_passage', 'unit': 'left/right/ambiguous', 'mandatory': True,
         'purpose': 'Continuous source-derived island side and physical island review status'}]
    channels = {'st.roundabout': 'st.roundabout', 'rel.bearing': 'rel.bearing',
                'rel.occupies': 'rel.occupies', 'kin.heading': 'kin.heading',
                'kin.position': 'kin.position'}
    for term, channel in channels.items():
        plan['source_observation_mapping'][term]['channels'] = [channel]
        plan['source_observation_mapping'][term]['evidence'] = (
            'Selected original Native 600-frame body/map/camera channel; physical island and pixels pending local review')
    plan['evidence_review'] = {
        'method': 'Frozen accepted memberships inspected without replay; no source-hashed original equivalence receipt supplied',
        'reviewer': 'worker source inventory', 'facts': [],
        'gaps': [{'id': 'continuous-right-of-island',
                  'requirement': 'NRS 484B.220(2) continuous right-of-island passage',
                  'source': 'inputs/' + HERE.name + '/assignment.json',
                  'why_existing_insufficient': 'Three accepted membership rows have no supplied original frame/map/pixel equivalence receipt'}]}
    for case in plan['cases']:
        case['gap_ids'] = ['continuous-right-of-island']
    write(plan_path, plan)

    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    manifest['status'] = 'selected_delivery_cpu_prepared'
    audit_script = HERE / 'delivery_audit_30s.py'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        positive = HERE / f'delivery-{suffix}-positive.log'
        negative = HERE / f'delivery-{suffix}-negative.log'
        expected_error = 'Original physical island, body passage and four camera pixels required for delivery acceptance'
        if expected_error not in negative.read_text():
            raise ValueError('Delivery negative did not reject unreviewed original source')
        command = '.venv-cpu/bin/python work/' + HERE.name + '/delivery_audit_30s.py --case ' + case_id
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ASSIGNMENT['selection_targets'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': audit_script.name, 'script_sha256': sha(audit_script),
            'command': command + ' --diagnostic', 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': command, 'negative_exit_code': 1,
            'negative_expected_error': expected_error,
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
        construction = json.loads((HERE / entry['construction']).read_text())
        names = [item['name'] for item in construction['recording_description']['channels']]
        config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
        atom_names = set(config['required_atoms']) | set(names)
        entry['acquisition'] = {
            atom: {'entrypoint': 'capture_30s.py',
                   'method': 'Original Native 20 Hz ego body, heading, velocity, map lane and four synchronized camera frame capture; saved finalizer derives island bearing',
                   'evidence': 'native-raw-actors.jsonl, native-map-readback.json, capture/evidence.jsonl, trace.jsonl, video_frames.jsonl and original four camera videos'}
            for atom in sorted(atom_names)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        saved_log = HERE / entry['saved_processing']['receipt']
        entry['post_capture'] = {
            'command': 'python runtime.py process-saved --manifest work/' + HERE.name +
                       '/execution-manifest.json --case ' + case_id +
                       ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$SAVED_OUTPUT"/v0001/feedback.json',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': entry['saved_processing']['receipt'],
            'test_log_sha256': sha(saved_log)}
    write(HERE / 'execution-manifest.json', manifest)

    source = json.loads((HERE / 'selected-construction-reference.json').read_text())
    files = {item['path']: item['content'] for item in source['files']}
    root_config = json.loads(files['config.json'])
    root_config['supported_case_ids'] = [case['case_id'] for case in manifest['cases']]
    files['config.json'] = json.dumps(root_config, indent=2, ensure_ascii=False) + '\n'
    source['files'] = [{'path': path, 'content': content} for path, content in files.items()]
    for path, content in files.items():
        dest = HERE / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    write(HERE / 'construction.json', source)

    comparison = {'comparison_id': plan['comparisons'][0]['comparison_id'],
                  'case_ids': [case['case_id'] for case in manifest['cases']],
                  'script': 'comparison_audit_30s.py',
                  'script_sha256': sha(HERE / 'comparison_audit_30s.py'),
                  'positive_command': '.venv-cpu/bin/python work/' + HERE.name +
                                      '/comparison_audit_30s.py --diagnostic',
                  'positive_exit_code': 0, 'positive_log': 'comparison-positive.log',
                  'positive_log_sha256': sha(HERE / 'comparison-positive.log'),
                  'negative_command': '.venv-cpu/bin/python work/' + HERE.name +
                                      '/comparison_audit_30s.py',
                  'negative_exit_code': 1, 'negative_log': 'comparison-negative.log',
                  'negative_log_sha256': sha(HERE / 'comparison-negative.log'),
                  'physical_island_verified': False,
                  'accepted_row_equivalence_claimed': False}
    write(HERE / 'comparison-audit-proof.json', comparison)
    print(json.dumps({'execution_manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json'),
                      'case_ids': comparison['case_ids']}))


if __name__ == '__main__':
    main()
