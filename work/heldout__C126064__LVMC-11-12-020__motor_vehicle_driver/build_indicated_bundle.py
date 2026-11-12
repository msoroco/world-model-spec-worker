"""Build the first exact, CARLA-lazy marked-turn construction.

This packages source code and CPU tests. A real site/authority record remains a
required capture input; no diagnostic claim is silently used for Native capture.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'heldout__C126064__LVMC-11-12-020__motor_vehicle_driver'
CASE = ASSIGNMENT + '__indicated_course'

ENTRY = '''"""Exact indicated-course entrypoint; site source is an explicit Native input."""
import argparse
import json
import os
from pathlib import Path
from native_runner import prepare, run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    if config['selected_case_id'] != 'CASE_ID' or config['rate_hz'] != 20 or config['frames'] != 160:
        raise ValueError('Exact marked-turn construction identity or duration changed')
    if args.check:
        if args.output_dir:
            raise ValueError('Offline check does not create Native output')
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    source = os.environ.get('MARKED_TURN_SITE_SOURCE')
    digest = os.environ.get('MARKED_TURN_SITE_SHA256')
    if not source or not digest:
        raise ValueError('Native capture requires explicit site source and SHA-256')
    plan = prepare(config['selected_case_id'], source, digest)
    run(plan, args.output_dir, args.host, args.port)

if __name__ == '__main__':
    main()
'''.replace('CASE_ID', CASE)


def build():
    description = {
        'channels': [{
            'name': 'original_marked_turn_course', 'unit': 'structured',
            'sampling_rate_hz': 20,
            'method': 'source-hashed physical marker readback, original four-camera images and joined full-body turn footprints',
            'time_window': 'all 160 frames over 8 s',
            'reference_frame': 'Native world coordinates and sourced intersection polygon',
            'uncertainty': 'municipal authorization, actual marker visibility and legal course conformance require original review'
        }],
        'context_inputs': ['independently reviewed site/authority record supplied at capture'],
        'limitations': ['CPU construction checks do not verify municipal authority or Native motion.']
    }
    cameras = [
        {'name': name, 'width': size[0], 'height': size[1],
         'pose_strategy': 'subject-mounted provisional marked-turn view', 'fov_deg': fov}
        for name, (_, _, size, fov) in __import__('marked_course_native').CAMERAS.items()
    ]
    config = {
        'selected_case_id': CASE, 'law_id': 'LVMC-11-12-020', 'cell_id': 'C126064',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 160,
        'duration_s': 8, 'required_atoms': [], 'source_packets': [],
        'cameras': cameras, 'case': {'case_id': CASE, 'recording_description': description},
        'engineering': {'target_speed_mps': 4.0, 'capture_frames': 160,
                        'source_selection': 'explicit_site_path_and_sha256'}
    }
    files = [
        {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
        {'path': 'runner.py', 'content': ENTRY},
    ]
    for name in ('native_runner.py', 'marked_course_native.py',
                 'turn_source_recorder.py', 'marked_course_measurement.py'):
        files.append({'path': name, 'content': (ROOT / name).read_text()})
    for test in sorted((ROOT / 'tests').glob('test*.py')):
        files.append({'path': 'tests/' + test.name, 'content': test.read_text()})
    proposal = {
        'format': 'worker-construction-proposal', 'case_id': CASE,
        'law_id': 'LVMC-11-12-020', 'cell_id': 'C126064',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'recording_description': description, 'files': files,
    }
    path = ROOT / 'indicated-construction.json'
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'cases': [{
            'case_id': CASE, 'kind': 'delivery',
            'construction': path.name, 'construction_sha256': digest,
            'candidate_risk': {'status': 'physical',
                               'reason': 'Marker readback and full turn through the sourced junction require Native verification.'},
            'candidates': [],
        }],
    }
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return digest


if __name__ == '__main__':
    print(build())
