"""Independent original-source and decoded-media audit for following delivery."""
import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure


ORIGINAL = ('following-history.jsonl', 'following-context.json',
            'following_samples.jsonl', 'surface_context.json',
            'trace.jsonl', 'video_frames.jsonl', 'acquisition.json', 'road.xodr')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def audit(attempt, processing, decode_receipt, case_id,
          media_verify=None, measure_fn=None):
    attempt = Path(attempt)
    processing = Path(processing)
    if not case_id.startswith('testing__C101303__NRS-484B-127-1__motor_vehicle_driver__'):
        raise ValueError('unknown exact following case')
    if (attempt/'fixture-provenance.json').exists() and read(
            attempt/'fixture-provenance.json').get('diagnostic_fixture') is True:
        raise ValueError('diagnostic fixture cannot establish Native delivery')
    required = set(ORIGINAL)|set(VIDEOS)
    seal = read(attempt/'capture-seal.json')
    if (seal.get('events') != ['capture_finished', 'encoders_closed',
                              'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('Native capture lifecycle incomplete')
    if not required <= set(seal.get('sources', {})):
        raise ValueError('Native seal omits original following source')
    for name, digest in seal['sources'].items():
        if not (attempt/name).is_file() or sha(attempt/name) != digest:
            raise ValueError('sealed original missing or changed: '+name)
    native_exit = read(attempt/'native-exit.json')
    if (native_exit.get('event') != 'native_exit' or
            native_exit.get('capture_seal_sha256') != sha(attempt/'capture-seal.json')):
        raise ValueError('Native exit does not bind capture seal')
    if not (attempt/'owner-release.json').is_file():
        raise ValueError('owner release missing')
    owner = read(attempt/'owner-release.json')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(attempt/'native-exit.json')):
        raise ValueError('owner release missing or stale')
    result = read(attempt/'result.json')
    if (result.get('case_id') != case_id or
            not all(result.get(key) is True for key in
                    ('setup_confirmed', 'behavior_attempted', 'maneuver_completed'))):
        raise ValueError('physical completion not confirmed for exact case')
    acquisition = read(attempt/'acquisition.json')
    for name in required-{'acquisition.json'}:
        source = acquisition.get(name, {})
        if source.get('kind') != 'original_native' or source.get('sha256') != sha(attempt/name):
            raise ValueError('original source absent or changed: '+name)
    history = rows(attempt/'following-history.jsonl')
    physical = rows(attempt/'following_samples.jsonl')
    trace = rows(attempt/'trace.jsonl')
    mapping = rows(attempt/'video_frames.jsonl')
    if (not history or len(history) != len(physical) or
            len(history) != len(trace) or len(history) != len(mapping)):
        raise ValueError('original following, physical, trace or video frame history incomplete')
    for index, (row, transition, motion, frame) in enumerate(
            zip(history, physical, trace, mapping)):
        identity = (frame.get('carla_frame'), frame.get('time_s'))
        if (frame.get('video_frame') != index or
                any((item.get('frame'), item.get('time_s')) != identity
                    for item in (row, transition, motion))):
            raise ValueError('original following/trace/camera frame join changed')
        if (transition.get('ego_body_vertices_m') != row.get('ego', {}).get('body_vertices_m') or
                transition.get('ego_lane_id') != row.get('lane_change', {}).get('ego_lane_id')):
            raise ValueError('original physical lane transition differs from following history')
        ego, leader = row.get('ego', {}), row.get('leader', {})
        other_ids = row.get('traffic_actor_ids')
        if (not isinstance(other_ids, list) or
                len(other_ids) != row.get('surrounding_vehicle_count', 0)-1 or
                len(set(other_ids)) != len(other_ids) or
                any(actor in (ego.get('actor_id'), leader.get('actor_id'))
                    for actor in other_ids)):
            raise ValueError('original surrounding traffic identities incomplete')
    measured = (measure_fn or measure)(attempt, case_id)
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
        checker = sha(Path(__file__).with_name('pixel_checks.py'))
        def media_verify(video, receipt, count, mapping_sha256):
            return verify_receipt(video, receipt, count,
                mapping_sha256=mapping_sha256,
                required_checks={'pixel_presence': checker})
    video = Path(saved.get('analysis_directory', ''))/'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    if not Path(decode_receipt).is_file():
        raise ValueError('source decode receipt missing')
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(attempt/'video_frames.jsonl'))
    context = read(attempt/'following-context.json')
    surface = read(attempt/'surface_context.json')
    route = context.get('common_following_route_xy_m')
    if (not isinstance(route, list) or len(route) < 2 or
            context.get('case_id') != case_id or
            surface.get('case_id') != case_id or
            surface.get('road_id') != context.get('road_id') or
            surface.get('following_lane_id') != context.get('following_lane_id') or
            surface.get('destination_lane_id') != context.get('target_lane_id') or
            context.get('route_source') != 'Native CARLA connected waypoints' or
            context.get('hill_crest', {}).get('source_ref') !=
            'Native CARLA map waypoint elevation'):
        raise ValueError('original connected hill route geometry missing')
    config = read(attempt/'config.json')
    if config.get('selected_case_id') != case_id:
        raise ValueError('original configuration selects another case')
    return {'format': 'worker-delivery-audit', 'passed': True,
            'case_id': case_id, 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor_id': config['actor'],
            'map_sha256': sha(attempt/'road.xodr'),
            'route_sha256': hashlib.sha256(json.dumps(route, sort_keys=True).encode()).hexdigest(),
            'camera_contract_sha256': hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest(),
            'duration_s': config['duration_s'], 'measurement': measured,
            'native_result_sha256': sha(attempt/'result.json'),
            'frame_count': len(mapping),
            'frame_map_sha256': sha(attempt/'video_frames.jsonl'),
            'video_sha256': sha(video),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt','processing','decode-receipt','case'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt,args.processing,
                           args.decode_receipt,args.case),indent=2))


if __name__ == '__main__':
    main()
