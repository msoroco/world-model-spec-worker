"""Independently check source-shaped roadway-return controller requests."""

import hashlib
import json
import math
from pathlib import Path

from build_entry_return import AID, FRAMES, POLICIES, ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(policy, root=ROOT):
    folder = Path(root) / 'native' / 'entry_return' / policy
    config = json.loads((folder / 'config.json').read_text())
    track = folder / 'requested-tracks.jsonl'
    rows = [json.loads(line) for line in track.read_text().splitlines()]
    if (config['case_id'] != AID + '__' + policy or
            config['controller_policy'] != policy or
            config['duration_s'] != 60 or config['rate_hz'] != 20 or
            config['route'] != 'road_exit_then_private_driveway_to_roadway' or
            config['site_road_sha256'] != sha(Path(root) / 'native/road/road.xodr') or
            config['requested_tracks_sha256'] != sha(track) or len(rows) != FRAMES):
        raise ValueError('Entry-return construction or source binding changed')
    for i, row in enumerate(rows):
        if (row['frame_index'] != i or
                abs(row['time_s'] - (i + 1) / 20) > 1e-6 or
                row['controller_policy'] != policy or
                row['phase'] not in {'road_exit', 'private_driveway_dwell',
                                     'roadway_entry'}):
            raise ValueError('Entry-return 20 Hz timeline differs')
        for name in ('requested_ego_world_xy_m',
                     'requested_approaching_world_xy_m',
                     'requested_pedestrian_world_xy_m'):
            point = row[name]
            if len(point) != 2 or any(type(x) not in (int, float) or
                                       not math.isfinite(x) for x in point):
                raise ValueError('Entry-return source geometry invalid')
        if type(row['requested_ego_speed_mps']) not in (int, float):
            raise ValueError('Entry-return ego controller speed invalid')
    return config, rows


def check(root=ROOT):
    a_cfg, a = read(POLICIES[0], root)
    b_cfg, b = read(POLICIES[1], root)
    fixed = ('law_id', 'cell_id', 'actor', 'site_road_sha256', 'route',
             'duration_s', 'rate_hz', 'roadway_entry_reference_y_m',
             'roadway_lane_y_m', 'sidewalk_world_y_interval_m',
             'source_review_required')
    if any(a_cfg[key] != b_cfg[key] for key in fixed):
        raise ValueError('Roadway-entry fixed site context differs')
    for i, (x, y) in enumerate(zip(a, b)):
        for key in ('frame_index', 'time_s', 'phase',
                    'requested_approaching_world_xy_m',
                    'requested_approaching_speed_mps',
                    'requested_pedestrian_world_xy_m'):
            if x[key] != y[key]:
                raise ValueError('Roadway-entry approaching context differs: '
                                 + str(i) + ':' + key)
        if i < 560 and (x['requested_ego_world_xy_m'] !=
                        y['requested_ego_world_xy_m'] or
                        x['requested_ego_speed_mps'] !=
                        y['requested_ego_speed_mps']):
            raise ValueError('Road exit and private driveway phases differ')
    if any(row['phase'] != 'road_exit' for row in a[:400]):
        raise ValueError('Original road-exit witness missing')
    if any(row['phase'] != 'private_driveway_dwell' for row in a[400:560]):
        raise ValueError('Private driveway dwell missing')
    if any(row['phase'] != 'roadway_entry' for row in a[560:]):
        raise ValueError('Roadway return phase missing')
    # The constructed policies differ before crossing the common sidewalk;
    # outcome and legal necessity remain unknown until original review.
    if not all(row['requested_ego_speed_mps'] == 0 for row in a[560:720]):
        raise ValueError('Requested yield dwell absent')
    if any(row['requested_ego_speed_mps'] == 0 for row in b[560:720]):
        raise ValueError('Requested no-dwell policy absent')
    if (a[-1]['requested_ego_world_xy_m'][1] != -1.75 or
            b[-1]['requested_ego_world_xy_m'][1] != -1.75):
        raise ValueError('Requested roadway return absent')
    # Confirm approaching vehicle is near the return crossing only in the
    # no-dwell request. This is engineering timing, never a legal threshold.
    no_wait_entry = next(i for i in range(560, FRAMES)
                         if b[i]['requested_ego_world_xy_m'][1] >= -3.5)
    wait_entry = next(i for i in range(560, FRAMES)
                      if a[i]['requested_ego_world_xy_m'][1] >= -3.5)
    if not (no_wait_entry < wait_entry and
            abs(b[no_wait_entry]['requested_approaching_world_xy_m'][0]) < 5 and
            abs(a[wait_entry]['requested_approaching_world_xy_m'][0]) > 5):
        raise ValueError('Approaching traffic timing difference not constructed')
    return {'format': 'roadway-entry-return-request-check', 'passed': True,
            'case_ids': [a_cfg['case_id'], b_cfg['case_id']],
            'frames_per_case': FRAMES, 'no_wait_entry_frame': no_wait_entry,
            'wait_entry_frame': wait_entry,
            'fixed_context': list(fixed),
            'deliberate_difference': 'pre_entry_yield_dwell',
            'actual_native_motion_observed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check()))
