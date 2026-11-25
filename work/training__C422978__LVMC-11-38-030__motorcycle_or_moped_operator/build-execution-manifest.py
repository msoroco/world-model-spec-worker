"""Bind selected exact constructions to their independently checked CPU receipts."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-30s-draft-execution-manifest.json'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main():
    manifest = json.loads(MANIFEST.read_text())
    manifest['status'] = 'selected_cpu_preparation'
    manifest['delivery_ready'] = False
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        physical_path = HERE / 'selected-30s/physical-proof' / witness / 'proof.json'
        entry['physical_preparation'] = {'case_id': entry['case_id'],
                                          'receipt': physical_path.relative_to(HERE).as_posix(),
                                          'sha256': sha(physical_path)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            'motorcycle_body_speed': {'entrypoint': 'runner.py',
                                      'method': 'original Native actor body and speed every 20 Hz frame',
                                      'evidence': 'native-observed.jsonl'},
            'sidewalk_lane_readback': {'entrypoint': 'runner.py',
                                       'method': 'original imported OpenDRIVE lane and body join',
                                       'evidence': 'native-map-readback.json and native-observed.jsonl'},
            'camera_frame_join': {'entrypoint': 'runner.py',
                                  'method': 'four synchronized original camera frame maps',
                                  'evidence': 'video_frames.jsonl and capture/evidence.jsonl'},
        }
        for candidate in [entry, *entry['candidates']]:
            candidate_id = candidate['id']
            proof = HERE / 'selected-30s/proof' / witness / candidate_id
            receipt = proof / 'compatibility.json'
            positive = proof / 'positive.log'
            negative = proof / 'negative.log'
            offline = proof / 'offline.log'
            for path in (receipt, positive, negative, offline):
                if not path.is_file():
                    raise ValueError(f'Missing selected proof: {path}')
            command = (f'{sys.executable} runtime.py offline --manifest {MANIFEST.relative_to(REPO)} '
                       f'--case {entry["case_id"]} --candidate {candidate_id} '
                       f'--output .runtime-work/c422978-selected/{witness}-{candidate_id}-offline-proof '
                       f'--python {sys.executable}')
            candidate['offline'] = {'command': command, 'exit_code': 0,
                                    'construction_sha256': candidate['construction_sha256'],
                                    'log': offline.relative_to(HERE).as_posix(),
                                    'log_sha256': sha(offline)}
            candidate['compatibility'] = {'receipt': receipt.relative_to(HERE).as_posix(),
                                          'sha256': sha(receipt),
                                          'log': positive.relative_to(HERE).as_posix(),
                                          'negative_log': negative.relative_to(HERE).as_posix()}
            candidate['negative'] = {'log': negative.relative_to(HERE).as_posix()}
        process = HERE / 'selected-30s/proof' / witness / 'primary/processing.json'
        if not process.is_file():
            raise ValueError(f'Missing selected saved processing receipt: {process}')
        entry['saved_processing'] = {'receipt': process.relative_to(HERE).as_posix(),
                                     'sha256': sha(process)}
        entry['post_capture'] = {
            'recorded_only': True,
            'command': (f'{sys.executable} runtime.py process-saved --manifest '
                        f'work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} '
                        '--attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" '
                        '--library runtime/library --validator "$DECODER" '
                        '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': process.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(process)}
        positive = HERE / 'selected-30s/delivery-proof' / (witness + '-positive.log')
        negative = HERE / 'selected-30s/delivery-proof' / (witness + '-negative.log')
        delivery = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': f'{sys.executable} work/{HERE.name}/delivery_audit.py --case {entry["case_id"]} --diagnostic',
            'negative_command': f'{sys.executable} work/{HERE.name}/delivery_audit.py --case {entry["case_id"]}',
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required for delivery acceptance',
            'test_log': positive.relative_to(HERE).as_posix(),
            'negative_log': negative.relative_to(HERE).as_posix(),
        }
        if positive.is_file() and negative.is_file():
            delivery['test_log_sha256'] = sha(positive)
            delivery['negative_log_sha256'] = sha(negative)
        entry['delivery_acceptance'] = delivery
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
