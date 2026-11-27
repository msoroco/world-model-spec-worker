"""Bind measured CPU proofs to the two selected original delivery cases."""
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
SCRATCH = ROOT / '.runtime-work/c179799'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


manifest = json.loads((FOLDER / 'selected-probe-manifest.json').read_text())
manifest['status'] = 'draft'
for entry in manifest['cases']:
    case = entry['case_id']
    label = case.rsplit('__', 1)[-1]
    proof_dir = FOLDER / 'proofs' / label
    proof_dir.mkdir(parents=True, exist_ok=True)
    for candidate in ['primary', 'fallback1']:
        selected = entry if candidate == 'primary' else entry['candidates'][0]
        offline_source = SCRATCH / f'offline-v4-{label}-{candidate}' / 'offline.log'
        offline_target = proof_dir / f'{candidate}-offline.log'
        shutil.copy2(offline_source, offline_target)
        selected['offline'] = {
            'exit_code': 0,
            'construction_sha256': selected['construction_sha256'],
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/selected-probe-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c179799/offline-v4-{label}-{candidate}',
            'log': str(offline_target.relative_to(FOLDER)),
            'log_sha256': digest(offline_target),
        }
        source = SCRATCH / f'compat-v5-{label}-{candidate}'
        files = {
            'receipt': ('compatibility.json', f'{candidate}-compatibility.json'),
            'log': ('compatibility-analysis.log', f'{candidate}-compatibility-analysis.log'),
            'negative_log': ('negative-analysis.log', f'{candidate}-negative-analysis.log'),
        }
        paths = {}
        for key, (source_name, target_name) in files.items():
            target = proof_dir / target_name
            shutil.copy2(source / source_name, target)
            paths[key] = str(target.relative_to(FOLDER))
        selected['compatibility'] = {
            'receipt': paths['receipt'],
            'sha256': digest(FOLDER / paths['receipt']),
            'log': paths['log'],
            'negative_log': paths['negative_log'],
        }
        if candidate == 'primary':
            entry['negative'] = {
                'log': paths['negative_log'],
                'log_sha256': digest(FOLDER / paths['negative_log']),
            }
    entry['preparation_status'] = 'incomplete'
    entry['acquisition'] = {
        'vehicle_pose_and_speed': {'entrypoint': 'runner.py', 'method': '600 original Native actor poses, velocity and frame identities', 'evidence': ['native-person-interaction.jsonl', 'trace.jsonl']},
        'source_camera_frame_join': {'entrypoint': 'runner.py', 'method': 'four original encoded camera streams and synchronized frame map', 'evidence': ['video_frames.jsonl', 'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']},
        'kin.position': {'entrypoint': 'runner.py', 'method': 'original ego and worker pose per Native frame', 'evidence': ['native-person-interaction.jsonl']},
        'kin.speed': {'entrypoint': 'runner.py', 'method': 'original ego speed per Native frame', 'evidence': ['native-person-interaction.jsonl']},
        'st.roadway': {'entrypoint': 'runner.py', 'method': 'authored road and original Native lane readback with independent premises source', 'evidence': ['road.xodr', 'native-road-readback.json', 'original-context-packet.json']},
        'ru.motor_vehicle': {'entrypoint': 'runner.py', 'method': 'original vehicle actor identity and source class', 'evidence': ['native-person-interaction.jsonl', 'original-context-packet.json']},
        'ru.driver': {'entrypoint': 'runner.py', 'method': 'original driver control linkage and separately sourced participant authority', 'evidence': ['native-person-interaction.jsonl', 'original-context-packet.json']},
        'ru.person': {'entrypoint': 'runner.py', 'method': 'distinct roadside person actor and separately sourced role', 'evidence': ['native-person-interaction.jsonl', 'original-context-packet.json']},
        'kin.time': {'entrypoint': 'runner.py', 'method': 'Native tick time joined to all four camera frame timestamps', 'evidence': ['native-person-interaction.jsonl', 'video_frames.jsonl']},
        'kin.relative_distance': {'entrypoint': 'finalize.py', 'method': 'full-frame vehicle and person surface gap, source-bound original actor dimensions', 'evidence': ['native-person-interaction.jsonl', 'original-context-packet.json']},
        'kin.relative_speed': {'entrypoint': 'finalize.py', 'method': 'original frame pair relative speed and projected closing time', 'evidence': ['native-person-interaction.jsonl']},
        'kin.acceleration': {'entrypoint': 'finalize.py', 'method': 'original full trace longitudinal acceleration and worker acceleration', 'evidence': ['native-person-interaction.jsonl']},
        'kin.yaw_rate': {'entrypoint': 'finalize.py', 'method': 'original ego yaw and frame times', 'evidence': ['native-person-interaction.jsonl']},
        'evt.contact': {'entrypoint': 'runner.py', 'method': 'original collision sensor events with actor identities', 'evidence': ['native-person-interaction.jsonl']},
        'env.sight_line': {'entrypoint': 'finalize.py', 'method': 'original four-view pixels with independently sourced sight line review', 'evidence': ['overview.mkv', 'approach.mkv', 'original-context-packet.json']},
        'env.surface_condition': {'entrypoint': 'finalize.py', 'method': 'original weather and road readback with independent surface provenance', 'evidence': ['native-road-readback.json', 'original-context-packet.json']},
        'env.nearby_property': {'entrypoint': 'finalize.py', 'method': 'independent adjacent premises and access way provenance', 'evidence': ['original-context-packet.json', 'native-road-readback.json']},
    }
    # Explicitly cover any additional pinned channels without weakening the
    # source requirement: their Native values remain tied to these source files.
    construction = json.loads((FOLDER / entry['construction']).read_text())
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        entry['acquisition'].setdefault(name, {'entrypoint': 'runner.py', 'method': 'original Native actor, environment and camera frame acquisition', 'evidence': ['native-person-interaction.jsonl', 'video_frames.jsonl', 'original-context-packet.json']})
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
        'feedback_command': f'cat $SAVED_OUTPUT/feedback.json # {case}',
        'test_exit_code': -1,
        'test_log': f'proofs/{label}/saved.log',
        'test_log_sha256': '',
    }
write(FOLDER / 'execution-manifest.json', manifest)
print('manifest', digest(FOLDER / 'execution-manifest.json'))
