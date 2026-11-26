"""Independent saved-source audit for one exact school-crossing-zone case."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, fixture, compatibility, processing):
    fixture = Path(fixture)
    required = ('school_zone_context.json', 'native_motion.jsonl', 'video_frames.jsonl',
                'children_context.jsonl') + tuple(camera + '.mkv' for camera in CAMERAS)
    for name in required:
        if not (fixture / name).is_file():
            raise ValueError('Missing original source: ' + name)
    context = json.loads((fixture / 'school_zone_context.json').read_text())
    if context.get('case_id') != case:
        raise ValueError('Source context selects another exact case')
    if context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Missing source provenance kind')
    if context['review_kind'] == 'original_source_review':
        survey = fixture / 'native_survey.json'
        if not survey.is_file() or sha(survey) != context.get('native_survey_sha256'):
            raise ValueError('Original zone/device survey is missing or changed')
        for field in ('reviewer', 'zone_designation_source', 'zone_sign_source',
                      'calendar_source', 'school_hours_source', 'beacon_source',
                      'beacon_phase_source', 'beacon_lights_source', 'vehicle_class_source'):
            if not context.get(field):
                raise ValueError('Original independent source review missing: ' + field)
    frame_rows = [json.loads(row) for row in (fixture / 'video_frames.jsonl').read_text().splitlines()]
    motion_rows = [json.loads(row) for row in (fixture / 'native_motion.jsonl').read_text().splitlines()]
    child_rows = [json.loads(row) for row in (fixture / 'children_context.jsonl').read_text().splitlines()]
    if not (len(frame_rows) == len(motion_rows) == len(child_rows) == 600):
        raise ValueError('Missing exact 600-frame participant source join')
    for i, (frame, motion, children) in enumerate(zip(frame_rows, motion_rows, child_rows)):
        if (frame.get('video_frame') != i or motion.get('video_frame') != i or
                children.get('video_frame') != i or
                frame.get('native_frame') != motion.get('native_frame') or
                frame.get('native_frame') != children.get('native_frame') or
                motion.get('ego_actor_id') != context.get('ego_actor_id') or
                {child.get('id') for child in children.get('children', [])} !=
                {'child_left', 'child_right'}):
            raise ValueError('Participant or time join differs from source')
    hashes = {}
    for camera in CAMERAS:
        path = fixture / (camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,r_frame_rate', '-of', 'json', str(path)],
                               capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('Source video decode failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != '600' or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Full source video differs: ' + camera)
        hashes[path.name] = sha(path)
    if hashes != context.get('camera_sha256'):
        raise ValueError('Source camera hashes differ from context')
    receipt = json.loads(Path(compatibility).read_text())
    processed = json.loads(Path(processing).read_text())
    if (receipt.get('case_id') != case or receipt.get('passed') is not True or
            receipt.get('analysis_report_sha256') is None or
            processed.get('passed') is not True or processed.get('recorded_only') is not True or
            processed.get('originals_preserved') is not True or processed.get('missing_evidence')):
        raise ValueError('Independent CPU processing or source audit failed')
    return {'case_id': case, 'source_sha256': {name: sha(fixture / name) for name in required},
            'frames': 600, 'participants': 3, 'full_source_video_decode': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--compatibility', required=True)
    parser.add_argument('--processing', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.fixture, args.compatibility, args.processing), sort_keys=True))


if __name__ == '__main__':
    main()
