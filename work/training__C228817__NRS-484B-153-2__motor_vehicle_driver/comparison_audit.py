"""Independent exact-source comparison of traffic arrival during door actions.

This audit checks fixed conditions and measured passing motion. Whether any
observed response is statutory interference remains a contextual review.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

PREFIX = 'training__C228817__NRS-484B-153-2__motor_vehicle_driver__'
PAIR = {'board': ('board_overlap', 'board_clear'),
        'alight': ('alight_overlap', 'alight_clear')}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def source(root):
    root = Path(root)
    config = read(root / 'config.json')
    review = read(root / 'door-pixel-review.json')
    trace = rows(root / 'native-door-trace.jsonl')
    mapping = rows(root / 'video_frames.jsonl')
    require(len(trace) == len(mapping) == 600, 'Complete original frame/time join required')
    require(review.get('case_id') == config.get('case_id') and len(review.get('door_observations', [])) == 600,
            'Exact original pixel review required')
    require(review.get('observed_door_side') == review.get('observed_traffic_side') == 'left',
            'Original traffic-side door differs')
    require(review.get('ground_plane_calibration_source'), 'Calibrated door geometry source required')
    for view in VIEWS:
        require(review.get('camera_sha256', {}).get(view) == sha(root / (view + '.mkv')),
                'Source camera hash differs: ' + view)
    first_tick = mapping[0]['native_frame']
    first_time = mapping[0]['native_elapsed_s']
    for i, (actor, frame) in enumerate(zip(trace, mapping)):
        require(actor['video_frame'] == frame['video_frame'] == i and
                actor['native_frame'] == frame['native_frame'] == first_tick + i and
                abs(actor['native_elapsed_s'] - frame['native_elapsed_s']) < 1e-5 and
                abs(frame['native_elapsed_s'] - first_time - i/20) < 1e-4,
                'Original frame/time join differs')
    moving = [i for i, row in enumerate(trace) if row.get('passing_speed_mps', 0) > 0.05]
    require(moving and all(trace[i].get('passing_lateral_offset_m', 0) > 0.25 for i in moving),
            'Moving passing traffic on traffic side required')
    events = review.get('transfer_events', [])
    require(len(events) == 1 and events[0].get('kind') == 'passenger' and
            events[0].get('video_frame') == 200 and
            events[0].get('occupancy_delta_observed') in (-1, 1),
            'Sourced boarding/alighting event required')
    opening = [i for i, row in enumerate(review['door_observations']) if row['door_open']]
    require(opening and opening[0] > 0 and opening[-1] < 599,
            'Complete original door interval required')
    require(opening[0] < events[0]['video_frame'] <= opening[-1],
            'Door opening must precede reviewed person transfer')
    opening_only_moving = [i for i in moving if opening[0] <= i < events[0]['video_frame']]
    return {'config': config, 'review': review, 'trace': trace, 'mapping': mapping,
            'moving': moving, 'opening': opening, 'opening_only_moving': opening_only_moving,
            'event': events[0],
            'source_sha256': sha(root / 'native-door-trace.jsonl'),
            'camera_sha256': {view: sha(root / (view + '.mkv')) for view in VIEWS}}


def compare(reference, contrast, action):
    require(action in PAIR, 'Unknown exact comparison action')
    left, right = source(reference), source(contrast)
    a, b = PAIR[action]
    require(left['config']['case_id'] == PREFIX+a and right['config']['case_id'] == PREFIX+b,
            'Exact comparison case order differs')
    for key in ('law_id', 'cell_id', 'actor', 'frozen_cell', 'cameras',
                'duration_frames', 'duration_s', 'rate_hz', 'transfer_kind',
                'occupancy_delta_requested'):
        require(left['config'][key] == right['config'][key], 'Fixed construction changed: '+key)
    require(left['config']['schedule'] != right['config']['schedule'],
            'Passing arrival schedule has no deliberate difference')
    for key in ('observed_door_side', 'observed_traffic_side', 'door_observations',
                'ground_plane_calibration_source'):
        require(left['review'][key] == right['review'][key], 'Fixed reviewed door source changed: '+key)
    require(left['event'] == right['event'], 'Fixed boarding or alighting event changed')
    require(left['opening'] == right['opening'], 'Observed door interval changed')
    require(left['moving'][0] < left['opening'][-1] and right['moving'][0] > right['opening'][-1],
            'Observed passing arrival did not bracket door action')
    require(left['opening_only_moving'] and not right['opening_only_moving'],
            'Opening-only moving-traffic contrast missing before transfer')
    require(left['source_sha256'] != right['source_sha256'], 'Distinct passing trace source required')
    return {'format':'worker-independent-door-passing-comparison','passed':True,
        'case_ids':[PREFIX+a,PREFIX+b],'source_sha256':[left['source_sha256'],right['source_sha256']],
        'fixed_conditions':['frozen cell and participant action','door state and geometry',
                            'camera plan and frame rate','passenger transfer frame and occupancy change'],
        'observed_passing_arrival_frames':[left['moving'][0],right['moving'][0]],
        'observed_door_open_frame':left['opening'][0],
        'observed_door_close_frame':left['opening'][-1]+1,
        'opening_only_before_transfer':{'frame_range':[left['opening'][0],left['event']['video_frame']-1],
            'moving_frames':[len(left['opening_only_moving']),len(right['opening_only_moving'])],
            'recording_reuse':'opening motion is measured before boarding or alighting in the same original recording'},
        'legal_interference_conclusion':None,'physical_acceptance_claimed':False}


def selftest():
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Scratch must be under .runtime-work')
    results=[]
    for action,(a,b) in PAIR.items():
        reference=scratch/('attempt-opening-'+a)
        contrast=scratch/('attempt-opening-'+b)
        positive=compare(reference,contrast,action)
        results.append(positive)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            altered=Path(temp)/'altered'
            shutil.copytree(contrast,altered)
            config=read(altered/'config.json')
            config['cameras'][0]['fov_deg']=75
            (altered/'config.json').write_text(json.dumps(config)+'\n')
            try:
                compare(reference,altered,action)
            except ValueError as error:
                require('Fixed construction changed: cameras' in str(error),
                        'Wrong fixed-condition rejection')
            else:
                raise AssertionError('Altered camera plan accepted')
    return {'format':'worker-door-passing-comparison-selftest','passed':True,
            'positive':results,'altered_camera_rejected':True}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--reference')
    parser.add_argument('--contrast')
    parser.add_argument('--action',choices=tuple(PAIR))
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(),sort_keys=True))
    else:
        result=compare(args.reference,args.contrast,args.action)
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'passed':True,'case_ids':result['case_ids']}))
