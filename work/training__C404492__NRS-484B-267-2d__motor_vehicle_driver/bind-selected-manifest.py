"""Bind exact current CPU proofs while retaining partial delivery status."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def relative(path):
    return path.relative_to(HERE).as_posix()


def main():
    manifest = read(HERE / 'current-probe-manifest.json')
    public = read(HERE / 'current/public-matrix.json')
    saved = read(HERE / 'current/saved-matrix.json')
    if not public['all_passed'] or not saved['all_passed']:
        raise ValueError('Current candidate proof matrix incomplete')
    public_by_id = {(x['case_id'], x['candidate_id']): x for x in public['results']}
    saved_by_id = {(x['case_id'], x['candidate_id']): x for x in saved['results']}
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        entry['acquisition'] = {
            'drv.responding_emergency': {
                'entrypoint': 'runner.py',
                'method': 'Record subject and authorized emergency vehicle identity, original pose and flashing phase on each Native frame',
                'evidence': 'vehicle_poses.jsonl and emergency_context.template.json; authorization and equipment require independent source review'},
            'rel.same_direction': {
                'entrypoint': 'runner.py',
                'method': 'Read back both observed driving-lane waypoints, travel heading and per-frame actor headings',
                'evidence': 'vehicle_poses.jsonl joined to video_frames.jsonl and reviewed lane context'},
            'rel.longitudinal_overlap': {
                'entrypoint': 'finalize.py',
                'method': 'Project original subject and emergency vehicle body extents onto observed travel axis and retain each overlapping frame',
                'evidence': 'vehicle_poses.jsonl, trace.jsonl and channels/rel.longitudinal_overlap.jsonl'},
            'drv.overtaking': {
                'entrypoint': 'finalize.py',
                'method': 'Track signed original relative order across frames separately from body overlap',
                'evidence': 'vehicle_poses.jsonl and channels/drv.overtaking.jsonl'},
            'rel.ahead_behind_in_lane': {
                'entrypoint': 'finalize.py',
                'method': 'Report signed relative longitudinal order and distinct adjacent lane identities',
                'evidence': 'vehicle_poses.jsonl and channels/rel.ahead_behind_in_lane.jsonl'},
            'kin.velocity': {
                'entrypoint': 'runner.py',
                'method': 'Retain observed per-frame actor velocities and ego trace at original Native frame and time',
                'evidence': 'vehicle_poses.jsonl and trace.jsonl joined to video_frames.jsonl'},
            'dev.human_direction': {
                'entrypoint': 'finalize.py',
                'method': 'Carry source-reviewed officer direction as structured context with unknown preserved',
                'evidence': 'officer_direction_context review and channels/context-review.json'},
        }
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': relative(physical),
                                         'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT',
                                   'survey_env_var': 'SCENARIO_NATIVE_SURVEY'}
        for candidate in ['primary', *entry['candidates']]:
            candidate_id = candidate if candidate == 'primary' else candidate['id']
            selected = entry if candidate_id == 'primary' else candidate
            key = (case_id, candidate_id)
            if key not in public_by_id or key not in saved_by_id:
                raise ValueError('Candidate proof missing: ' + str(key))
            pub, save = public_by_id[key], saved_by_id[key]
            if (pub['construction_sha256'] != selected['construction_sha256']
                    or save['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Candidate source hash differs: ' + str(key))
            name = suffix + '-' + candidate_id
            offline = HERE / 'current-offline' / (name + '.log')
            receipt = HERE / pub['receipt']
            analysis = HERE / 'current-public' / (name + '-analysis.log')
            negative = HERE / 'current-public' / (name + '-negative.log')
            processed = HERE / save['receipt']
            if (sha(receipt) != pub['sha256'] or sha(processed) != save['sha256']
                    or sha(analysis) != pub['analysis_log_sha256']
                    or sha(negative) != pub['negative_log_sha256']):
                raise ValueError('Returned candidate proof changed: ' + name)
            selected['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/'
                    + HERE.name + '/execution-manifest.json --case ' + case_id
                    + ' --candidate ' + candidate_id + ' --output "$OFFLINE_OUT"'
                    + ' --python .venv-cpu/bin/python',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': relative(offline), 'log_sha256': sha(offline)}
            selected['compatibility'] = {'receipt': relative(receipt),
                                         'sha256': sha(receipt),
                                         'log': relative(analysis),
                                         'negative_log': relative(negative)}
            selected['negative'] = {'log': relative(negative)}
            selected['saved_processing'] = {'receipt': relative(processed),
                                            'sha256': sha(processed)}
        primary = HERE / 'current-saved' / (suffix + '-primary-receipt.json')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/'
                + HERE.name + '/execution-manifest.json --case ' + case_id
                + ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"'
                + ' --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': relative(primary),
            'test_log_sha256': sha(primary)}
    manifest['status'] = 'partial_selected_cpu_proofs_bound'
    manifest['delivery_ready'] = False
    target = HERE / 'execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'candidate_proofs': len(public_by_id),
                      'sha256': sha(target), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
