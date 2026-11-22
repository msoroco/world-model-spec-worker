"""Independent saved original-source and media audit for a left-arrow delivery."""
import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure

ORIGINAL = ('turn-history.jsonl', 'intersection-context.json', 'trace.jsonl',
            'video_frames.jsonl', 'acquisition.json', 'road.xodr')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def audit(attempt, processing, decode_receipt, case_id, media_verify=None):
    attempt = Path(attempt)
    processing = Path(processing)
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in ('crosswalk_clear_turn', 'crosswalk_occupied_yield'):
        raise ValueError('unknown exact left-arrow case')
    required = set(ORIGINAL) | set(VIDEOS)
    if suffix == 'crosswalk_occupied_yield':
        required.add('pedestrian-entry.jsonl')
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('events') != ['capture_finished', 'encoders_closed',
                              'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('Native capture lifecycle incomplete')
    if not required <= set(seal.get('sources', {})):
        raise ValueError('Native seal omits original left-arrow source')
    for name, digest in seal['sources'].items():
        if not (attempt / name).is_file() or sha(attempt / name) != digest:
            raise ValueError('sealed original missing or changed: ' + name)
    native_exit = read(attempt / 'native-exit.json')
    if (native_exit.get('event') != 'native_exit' or
            native_exit.get('capture_seal_sha256') != sha(attempt / 'capture-seal.json')):
        raise ValueError('Native exit does not bind capture seal')
    if not (attempt / 'owner-release.json').is_file():
        raise ValueError('owner release missing')
    owner = read(attempt / 'owner-release.json')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(attempt / 'native-exit.json')):
        raise ValueError('owner release missing or stale')
    result = read(attempt / 'result.json')
    if (result.get('case_id') != case_id or
            not all(result.get(key) is True for key in
                    ('setup_confirmed', 'behavior_attempted', 'maneuver_completed'))):
        raise ValueError('physical completion not confirmed for exact case')
    acquisition = read(attempt / 'acquisition.json')
    for name in required - {'acquisition.json'}:
        source = acquisition.get(name, {})
        if source.get('kind') != 'original_native' or source.get('sha256') != sha(attempt / name):
            raise ValueError('original source absent or changed: ' + name)
    turn = rows(attempt / 'turn-history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    if not turn or len(turn) != len(trace) or len(turn) != len(mapping):
        raise ValueError('original turn, trace or video frame history incomplete')
    for index, (row, motion, frame) in enumerate(zip(turn, trace, mapping)):
        identity = (frame.get('carla_frame'), frame.get('time_s'))
        if (frame.get('video_frame') != index or
                any((item.get('frame'), item.get('time_s')) != identity
                    for item in (row, motion))):
            raise ValueError('original turn/trace/camera frame join changed')
    measured = measure(attempt, suffix)
    saved = read(processing)
    if (saved.get('format') != 'worker-saved-processing' or
            saved.get('passed') is not True or saved.get('recorded_only') is not True):
        raise ValueError('saved processing receipt absent or failed')
    saved_result = Path(saved.get('result', ''))
    if (not saved_result.is_file() or
            saved.get('result_sha256') != sha(saved_result) or
            read(saved_result).get('case_id') != case_id):
        raise ValueError('saved result missing, stale or wrong case')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    video = Path(saved.get('analysis_directory', '')) / 'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    if not Path(decode_receipt).is_file():
        raise ValueError('source decode receipt missing')
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    context = read(attempt / 'intersection-context.json')
    route = context.get('route_waypoints')
    if (not isinstance(route, list) or len(route) != 4 or
            any(not all(k in point for k in ('x_m', 'y_m', 'road_id', 'lane_id'))
                for point in route)):
        raise ValueError('original connected left-turn route geometry missing')
    config = read(attempt / 'config.json')
    if config.get('selected_case_id') != case_id:
        raise ValueError('original configuration selects another case')
    return {'format': 'worker-delivery-audit', 'passed': True,
            'case_id': case_id, 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor_id': config['actor'],
            'map_sha256': sha(attempt / 'road.xodr'),
            'route_sha256': hashlib.sha256(json.dumps(route, sort_keys=True).encode()).hexdigest(),
            'camera_contract_sha256': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
            'duration_s': config['duration_s'], 'measurement': measured,
            'native_result_sha256': sha(attempt / 'result.json'),
            'frame_count': len(mapping),
            'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'video_sha256': sha(video),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'processing', 'decode-receipt', 'case'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing,
                           args.decode_receipt, args.case), indent=2))


if __name__ == '__main__':
    main()
