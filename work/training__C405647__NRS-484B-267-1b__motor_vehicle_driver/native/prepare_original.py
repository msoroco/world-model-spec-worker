"""Bridge retained original Native capture into saved right-edge geometry.

This processor never infers qualifying lamps, vehicle authority, officer
direction, a lawful shoulder sign, or a legal outcome from CARLA controls.
"""
import argparse
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path

from measure_saved import AID, FRAME, HERE, _verify_original_cameras, assignment_hash, measure, sha

CAMERAS = ('overview', 'front_lamp', 'right_edge', 'rear_approach')


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _authored(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Native coordinate absent')
    x, y = map(float, value)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError('Native coordinate nonfinite')
    return [x, -y]


def prepare(source, destination, case, candidate):
    source, destination = Path(source), Path(destination)
    if case not in ('reference', 'contrast') or candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown case or candidate')
    if destination.exists():
        raise ValueError('Retain existing saved packet; choose new destination')
    config = json.loads((source / 'config.json').read_text())
    if config.get('case_id') != AID + '__' + case or config.get('candidate_id') != candidate:
        raise ValueError('Original capture bundle identity differs')
    draft = HERE / 'config.json'
    if not draft.is_file():
        draft = HERE / 'drafts' / case / candidate / 'config.json'
    if sha(source / 'config.json') != sha(draft):
        raise ValueError('Original capture bundle differs from exact CPU construction')
    report = json.loads((source / 'native-capture-report.json').read_text())
    if (report.get('case_suffix') != case or report.get('candidate_id') != candidate or
        report.get('frames') != 480 or report.get('error') is not None or
        report.get('restoration') is None or report.get('accepted') is not False):
        raise ValueError('Native capture incomplete or unsealed')
    readback = json.loads((source / 'native-map-readback.json').read_text())
    if readback.get('observed_initial_lanes') != {'subject': -1, 'approach': -1}:
        raise ValueError('Native initial lane readback differs')
    if any(not (source / (name + '.mkv')).is_file() for name in CAMERAS):
        raise ValueError('Original camera source absent')
    camera_sha = {name: sha(source / (name + '.mkv')) for name in CAMERAS}
    scope = {'assignment_sha256': assignment_hash(),
             'case_suffix': case, 'candidate_id': candidate,
             'coordinate_frame': FRAME, 'source_kind': 'original_native',
             'camera_sha256': camera_sha, 'original_camera_decode_verified': True,
             'native_source_hashes': {name: sha(source / name) for name in
                                      ('config.json', 'native-capture-report.json',
                                       'native-map-readback.json', 'observed-actors.jsonl',
                                       'video_frames.jsonl')},
             'vehicle_authority_or_lamp_qualification_verified': False,
             'physical_success_claimed': False}
    _verify_original_cameras(source, scope)
    actors = _rows(source / 'observed-actors.jsonl')
    frames = _rows(source / 'video_frames.jsonl')
    if len(actors) != 480 or len(frames) != 480:
        raise ValueError('Original actor/video frame count differs')
    saved = []
    first_time = None
    for index, (actor, video) in enumerate(zip(actors, frames)):
        native_frame = actor.get('native_frame')
        if (actor.get('frame') != index or video.get('video_frame') != index or
            video.get('native_frame') != native_frame or video.get('carla_frame') != native_frame or
            actor.get('source_kind') != 'original_native'):
            raise ValueError('Original actor/video frame join differs')
        time = float(actor['time_s'])
        if first_time is None:
            first_time = time
        if not math.isfinite(time) or abs(time - first_time - index / 20) > .01 or abs(float(video['time_s']) - time) > .001:
            raise ValueError('Original actor/video time join differs')
        if actor.get('front_red_flash_on') is not None:
            raise ValueError('Native light control substituted for pixel review')
        participants = actor.get('actors', {})
        subject, approach = participants.get('subject'), participants.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('Original participant absent')
        saved.append({'frame': index, 'native_frame': native_frame,
                      'video_frame': index, 'time_s': index / 20,
                      'coordinate_frame': FRAME, 'source_kind': 'original_native',
                      'subject': {'center_xy_m': _authored(subject['native_center_xy_m']),
                                  'body_xy_m': [_authored(v) for v in subject['native_body_xy_m']],
                                  'speed_mps': subject['native_speed_mps'],
                                  'heading_deg': -subject['native_yaw_deg']},
                      'approach': {'center_xy_m': _authored(approach['native_center_xy_m'])}})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        folder = Path(temporary)
        for name in (*[camera + '.mkv' for camera in CAMERAS],
                     'config.json', 'native-capture-report.json',
                     'native-map-readback.json', 'observed-actors.jsonl', 'video_frames.jsonl'):
            shutil.copyfile(source / name, folder / name)
        (folder / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
        (folder / 'actor-frames.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in saved))
        receipt = measure(folder)
        (folder / 'saved-geometry.json').write_text(json.dumps(receipt, indent=2) + '\n')
        folder.rename(destination)
    return {'saved_packet': str(destination), 'measurement': receipt,
            'original_capture_processed': True, 'accepted_delivery': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.destination, args.case, args.candidate), indent=2))
