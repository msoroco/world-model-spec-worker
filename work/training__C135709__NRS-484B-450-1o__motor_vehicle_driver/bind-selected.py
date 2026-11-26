"""Bind selected device-zone proof chain and source acquisition without legal claims."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_device_authority_activity_and_exception_review'
    evidence = {
        'ego_pose': ['vehicle-poses.jsonl', 'video_frames.jsonl'],
        'device_prohibited_place_occupancy': ['road.xodr', 'device-review.json', 'vehicle-poses.jsonl'],
        'device_identity': ['road.xodr', 'device-inventory.json', 'device-review.json', 'overview.mkv'],
        'device_authority': ['device-review.json', 'overview.mkv'],
        'device_instruction_and_scope': ['device-review.json', 'road.xodr'],
        'device_condition': ['condition-review.json', 'device-review.json'],
        'civil_time': ['condition-review.json', 'video_frames.jsonl'],
        'vehicle_activity': ['activity-review.json', 'vehicle-poses.jsonl'],
        'traffic_conflict_context': ['exception-review.json', 'overview.mkv'],
        'law_compliance_context': ['exception-review.json'],
        'police_direction_context': ['exception-review.json', 'overview.mkv'],
        'device_direction_context': ['exception-review.json', 'device-review.json'],
        'source_camera_frame_join': ['video_frames.jsonl', 'overview.mkv']}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'physical-preparation.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py',
            'method': 'original Native frame/source join plus independent review for ' + name,
            'evidence': sources} for name, sources in evidence.items()}
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']}
        if (proof / 'saved.log').is_file():
            entry['post_capture'].update(test_log=str((proof / 'saved.log').relative_to(HERE)),
                test_log_sha256=sha(proof / 'saved.log'), test_exit_code=0)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(first, indent=2) + '\n')
    print({'cases': len(manifest['cases']), 'fallbacks': sum(len(row['candidates']) for row in manifest['cases'])})


if __name__ == '__main__':
    main()
