"""Bind selected parking proof chain and source acquisition without legal claims."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_park_vehicle_and_exception_review'
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'physical-preparation.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            'vehicle_pose_and_speed': {'entrypoint': 'runner.py', 'method': 'original actor pose and speed with Native frame identities', 'evidence': ['vehicle-poses.jsonl']},
            'park_frontage_geometry': {'entrypoint': 'runner.py', 'method': 'original street and frontage readback with reviewed park status', 'evidence': ['road.xodr', 'frontage-inventory.json', 'park-review.json']},
            'source_camera_frame_join': {'entrypoint': 'runner.py', 'method': 'four original RGB streams joined to Native frame map', 'evidence': ['video_frames.jsonl', 'overview.mkv']},
            'st.roadway': {'entrypoint': 'runner.py', 'method': 'original surveyed road and park frontage', 'evidence': ['road.xodr', 'frontage-inventory.json']},
            'ru.commercial_motor_vehicle': {'entrypoint': 'runner.py', 'method': 'original vehicle identity with independent commercial specification', 'evidence': ['vehicle-poses.jsonl', 'vehicle-spec-review.json']},
            'kin.extent': {'entrypoint': 'runner.py', 'method': 'original body extent and separately sourced overall length', 'evidence': ['vehicle-poses.jsonl', 'vehicle-spec-review.json']},
            'drv.standing_or_parked': {'entrypoint': 'runner.py', 'method': 'original 600-frame speed and rest interval', 'evidence': ['vehicle-poses.jsonl', 'video_frames.jsonl']},
            'dev.regulatory_sign': {'entrypoint': 'runner.py', 'method': 'original overview pixels with independent sign authority and permission review', 'evidence': ['overview.mkv', 'exception-review.json']},
            'kin.time': {'entrypoint': 'runner.py', 'method': 'original Native frame/time join', 'evidence': ['vehicle-poses.jsonl', 'video_frames.jsonl']}}
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
