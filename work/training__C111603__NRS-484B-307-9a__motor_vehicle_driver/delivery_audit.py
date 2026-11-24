"""Independent source and lifecycle audit for NRS 484B.307(9)(a) attempts.

Diagnostic mode exercises source joins without asserting physical or legal acceptance.
Original mode additionally requires the source-hashed Native frame and human review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decode(path):
    proc = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams',
        'v:0', '-show_entries', 'stream=codec_name,nb_read_frames,width,height',
        '-of', 'json', str(path)], capture_output=True, text=True, timeout=180)
    if proc.returncode:
        raise ValueError('Source camera decode failed: ' + path.name)
    streams = json.loads(proc.stdout).get('streams', [])
    if len(streams) != 1 or streams[0].get('nb_read_frames') != '600':
        raise ValueError('Source camera frame count differs: ' + path.name)
    if streams[0].get('codec_name') != 'ffv1':
        raise ValueError('Source camera is not FFV1: ' + path.name)
    return {k: streams[0].get(k) for k in ('codec_name', 'nb_read_frames', 'width', 'height')}


def audit(case, candidate, attempt, processing_path, diagnostic, review_path=None):
    attempt = Path(attempt).resolve()
    processing = read(processing_path)
    selected = read(required(attempt, 'candidate-selection.json'))
    if (selected.get('case_id') != case or selected.get('candidate_id') != candidate or
            processing.get('case_id') != case or processing.get('candidate_id') != candidate):
        raise ValueError('Selected case or candidate identity differs')
    if (processing.get('passed') is not True or processing.get('recorded_only') is not True or
            processing.get('originals_preserved') is not True or
            processing.get('timestamp_joins', {}).get('passed') is not True or
            processing.get('physical_acceptance_claimed') is not False or
            processing.get('legal_acceptance_claimed') is not False):
        raise ValueError('Recorded-only source proof or acceptance boundary differs')
    sources = processing.get('original_source_hashes', {})
    for name in ('native-raw-actors.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl',
                 'native-map-readback.json', 'native-capture-report.json'):
        path = required(attempt, name)
        if sha(path) != sources.get(name):
            raise ValueError('Original source hash differs: ' + name)
    native = rows(attempt / 'native-raw-actors.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    if len(native) != len(frame_map) or len(native) != len(evidence) or len(native) != 600:
        raise ValueError('Incomplete original actor/video/evidence join')
    for index, (actor, frame, observation) in enumerate(zip(native, frame_map, evidence)):
        if (actor.get('frame') != index or frame.get('video_frame') != index or
                actor.get('native_frame') != frame.get('native_frame') or
                observation.get('actor_id') != actor.get('ego', {}).get('actor_id') or
                not actor.get('other_vehicle', {}).get('actor_id')):
            raise ValueError('Original participant/frame join differs at %d' % index)
    cameras = {}
    for name in CAMERAS:
        video = required(attempt, name + '.mkv')
        if sha(video) != sources.get(name + '.mkv'):
            raise ValueError('Source camera hash changed: ' + name)
        cameras[name] = decode(video)
    result = read(required(attempt, 'result.json'))
    if result.get('case_id') != case or result.get('accepted') is not False:
        raise ValueError('Result identity or acceptance boundary changed')
    original = None
    if not diagnostic:
        if review_path is None:
            raise ValueError('Original source review required')
        native_dir = Path(__file__).resolve().parent / 'native'
        sys.path.insert(0, str(native_dir))
        from process_original import REVIEW_FLAGS, process
        bundle = attempt / 'work' / Path(__file__).resolve().parent.name / 'native' / 'drafts' / case.rsplit('__', 1)[-1] / candidate
        original = process(bundle, attempt, review_path)
        if not original.get('original_native_observed') or not all(original.get(flag) for flag in REVIEW_FLAGS):
            raise ValueError('Original arrow, governance, traffic or yielding review incomplete')
    return {'format': 'c111603-delivery-source-audit', 'case_id': case,
        'candidate_id': candidate, 'diagnostic_fixture': diagnostic,
        'frames_joined': 600, 'participants_joined': ['ego', 'other_vehicle'],
        'source_camera_decodes': cameras,
        'source_complete_for_diagnostic': True,
        'original_review_complete': original is not None,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
        'unverified': [] if original is not None else ['arrow pixels', 'governing direction',
            'lawful presence', 'physical yield', 'original Native provenance']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--review')
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    report = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
