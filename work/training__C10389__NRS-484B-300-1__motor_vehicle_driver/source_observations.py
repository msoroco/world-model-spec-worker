"""Convert original Native readback into typed channels without legal inference."""
import json
from pathlib import Path

TERMS = ('dev.traffic_signal', 'dev.regulatory_sign', 'dev.stop_sign',
         'dev.yield_sign', 'dev.speed_limit_sign', 'dev.lane_control_signal',
         'dev.governs', 'dev.position', 'kin.velocity', 'rel.occupies',
         'dev.human_direction')


def rows(native):
    native = Path(native)
    report = json.loads((native / 'native-capture-report.json').read_text())
    if report.get('error') is not None or report.get('observed_frames') != 600 or report.get('requested_frames') != 600 or not isinstance(report.get('restoration'), dict) or report['restoration'].get('restored') is not True:
        raise ValueError('Complete restored original Native attempt required')
    map_row = json.loads((native / 'native-map-readback.json').read_text())
    if map_row.get('source_kind') != 'original_native':
        raise ValueError('Original Native map readback required')
    signal = map_row['stop_landmark_readback']
    if not map_row['stop_landmark_verified'] or signal['id'] != '3891' or signal['type'] != '206':
        raise ValueError('Original Native stop landmark absent')
    actors = (json.loads(line) for line in (native / 'native-raw-actors.jsonl').read_text().splitlines())
    videos = (json.loads(line) for line in (native / 'video_frames.jsonl').read_text().splitlines())
    count = 0
    for actor, video in zip(actors, videos):
        if actor.get('source_kind') != 'original_native':
            raise ValueError('Original Native actor readback required')
        if actor['frame'] != video['video_frame'] or actor['native_frame'] != video['native_frame']:
            raise ValueError('Native actor/video frame join failed')
        ego = actor['ego']
        channels = {
            'dev.traffic_signal': None,
            'dev.regulatory_sign': {'map_type': '206', 'source': 'Native landmark; image classification pending'},
            'dev.stop_sign': {'landmark_id': signal['id'], 'map_type': signal['type'], 'physical_face_reviewed': False},
            'dev.yield_sign': None,
            'dev.speed_limit_sign': None,
            'dev.lane_control_signal': None,
            'dev.governs': {'ego_road_id': actor['observed_road_id'], 'ego_lane_id': actor['observed_lane_id'], 'device_road_id': signal['road_id'], 'applicability_verified': False},
            'dev.position': {'device_s_m': signal['s_m'], 'ego_center_native_xyz_m': ego['center_native_xyz_m']},
            'kin.velocity': {'native_xyz_mps': ego['velocity_native_xyz_mps'], 'speed_mps': ego['speed_mps']},
            'rel.occupies': {'body_native_xyz_m': ego['body_native_xyz_m'], 'ego_road_id': actor['observed_road_id'], 'ego_lane_id': actor['observed_lane_id']},
            'dev.human_direction': {'police_direction_verified': False, 'review_status': 'original video and actor inventory pending'},
        }
        if set(channels) != set(TERMS):
            raise ValueError('Missing source observation channel')
        count += 1
        yield {'frame': actor['frame'], 'native_frame': actor['native_frame'],
               'time_s': actor['time_s'], 'source_kind': 'original_native',
               'channels': channels, 'official_placement_verified': False,
               'legal_verdict': None}
    if count != 600:
        raise ValueError('Original Native observation window incomplete')


def write(native):
    native = Path(native)
    with (native / 'source-observations.jsonl').open('x') as stream:
        for row in rows(native):
            stream.write(json.dumps(row, allow_nan=False) + '\n')
