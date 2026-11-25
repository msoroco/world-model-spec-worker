"""Synthetic source-shaped direction fixtures; no Native outcome is claimed."""
import argparse
import json
import math
from pathlib import Path
from build_draft import requested_track
from finalize import analyze, finalize
from geometry import open_drive

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in values))


def create(root, probe):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    case = 'training__C238396__LVMC-11-43-010-A__motor_vehicle_driver__' + probe
    direction = 'counterclockwise' if probe == 'probe_a' else 'clockwise'
    config = {'case_id': case, 'selected_case_id': case,
              'law_id': 'LVMC-11-43-010-A', 'cell_id': 'C238396',
              'rate_hz': 20, 'duration_s': 30, 'requested_direction': direction,
              'recording_description': {'channels': [], 'context_inputs': [],
                                        'limitations': ['synthetic CPU fixture']}}
    (root / 'config.json').write_text(json.dumps(config) + '\n')
    (root / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'native_executed': False}) + '\n')
    (root / 'road.xodr').write_text(open_drive())
    (root / 'roundabout-map-readback.json').write_text(json.dumps({
        'source_kind': 'native_map_readback', 'samples': [{'road_id': 21},
                                                          {'road_id': 23}]}) + '\n')
    request = requested_track(direction)
    raw, controls, frames, trace = [], [], [], []
    for i, row in enumerate(request):
        ego_x, ego_y = (round(v, 4) for v in row['ego_xy_m'])
        other_x, other_y = (round(v, 4) for v in row['other_vehicle_xy_m'])
        actors = []
        for role, ident, x, y, speed, radius in (
                ('ego', 1, ego_x, ego_y, 4.0, 16.75),
                ('other', 2, other_x, other_y, 3.0, 20.25)):
            angle = math.atan2(y, x - 22)
            actors.append({'role': role, 'actor_id': ident,
                'blueprint_id': 'vehicle.synthetic.cpu', 'x_m': x, 'y_m': y,
                'yaw_deg': round(math.degrees(angle + (math.pi / 2 if role == 'other' or
                    direction == 'counterclockwise' else -math.pi / 2)), 3),
                'speed_mps': speed, 'bbox_half_length_m': 2.0,
                'bbox_half_width_m': 1.0,
                'road_id': 21 if -math.pi / 2 <= angle < 0 else 23,
                'lane_id': -1})
        frame = 1000 + i
        t = (i + 1) / 20
        raw.append({'video_frame': i, 'native_frame': frame, 'time_s': t,
                    'case_id': case, 'actors': actors})
        controls.append({'video_frame': i, 'native_frame': frame, 'time_s': t,
            'controls': {'ego': {'target_xy_m': [ego_x, ego_y],
                                 'target_speed_mps': 4.0},
                         'other': {'target_xy_m': [other_x, other_y],
                                   'target_speed_mps': 3.0}}})
        frames.append({'video_frame': i, 'carla_frame': frame,
            'native_frame': frame, 'time_s': t,
            'camera_native_frames': {name: frame for name in CAMERAS}})
        trace.append({'frame': frame, 'time_s': t,
            'position': {'x': ego_x, 'y': ego_y, 'z': 0},
            'heading_deg': actors[0]['yaw_deg'], 'speed_mps': 4.0})
    for name, values in (('native-raw-actors.jsonl', raw),
                         ('control-intent.jsonl', controls),
                         ('video_frames.jsonl', frames), ('trace.jsonl', trace)):
        write_rows(root / name, values)
    for camera in CAMERAS:
        (root / (camera + '.mkv')).write_text('CPU fixture placeholder, not footage\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    summary = {}
    for probe in ('probe_a', 'probe_b'):
        attempt = output / probe
        create(attempt, probe)
        metric = analyze(attempt)
        expected = 'counterclockwise' if probe == 'probe_a' else 'clockwise'
        if metric['direction']['translational_direction'] != expected:
            raise ValueError('Source direction differs')
        missing = output / (probe + '-missing')
        create(missing, probe)
        (missing / 'roundabout-map-readback.json').unlink()
        try:
            analyze(missing)
        except ValueError as error:
            if str(error) != 'Missing required source: roundabout-map-readback.json':
                raise
        else:
            raise ValueError('Missing source accepted')
        summary[probe] = {'direction': expected,
                          'cross_sum_m2': metric['direction']['signed_radial_cross_sum_m2']}
    print(json.dumps({'format': 'c238396-source-direction-proof-v1',
                      'probes': summary, 'native_executed': False,
                      'physical_or_legal_acceptance': False}, sort_keys=True))


if __name__ == '__main__':
    main()
