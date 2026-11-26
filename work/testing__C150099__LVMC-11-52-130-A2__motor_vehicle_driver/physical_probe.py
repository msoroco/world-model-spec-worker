"""Measure synthetic fire-lane maneuver fixtures from original-frame sources.

This is a CPU construction test. It cannot establish official designation,
physical camera visibility, or any legal classification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from fire_lane import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def source(case_id: str, kind: str, destination: Path) -> None:
    if destination.exists():
        raise ValueError('retain prior physical fixture; choose a fresh destination')
    destination.mkdir(parents=True)
    suffix = case_id.removeprefix(ROOT.name + '__')
    spec = json.loads((ROOT / ('diagnostic-' + suffix + '.json')).read_text())
    first = json.loads(spec['files']['original-attempt/history.jsonl'].splitlines()[0])
    site = json.loads(spec['files']['original-attempt/site.json'])
    case = next(item for item in CASES if item.id == suffix)
    write(destination / 'site.json', site)
    mapping, history, trace = [], [], []
    for index in range(900):
        frame = 1000 + index
        time_s = index / 20
        row = dict(first, original_frame=frame, time_s=time_s)
        row['camera_frames'] = {name: {'original_frame': frame,
                                        'source_sha256': packet['source_sha256']}
                                for name, packet in first['camera_frames'].items()}
        inside = case.target_region == 'inside'
        if kind == 'incomplete_motion' and case.sweep_kind == 'none':
            inside = not inside
        body = [11.0, 15.0] if inside else [31.0, 35.0]
        if case.sweep_kind == 'posted_offset':
            centre = site['posted_interval_m'][1] + case.sweep_setpoint_m
            if kind == 'incomplete_motion':
                centre += 4.0
            body = [centre - 2.0, centre + 2.0]
            row['reviewed_posted_end_x_m'] = site['posted_interval_m'][1]
        if case.sweep_kind == 'conflict_gap':
            row['actual_actor_body_gap_m'] = case.sweep_setpoint_m + (
                4.0 if kind == 'incomplete_motion' else 0.0)
            row['traffic_conflict_source_sha256'] = site['traffic_conflict_source_sha256']
        row['body_west_x_m'], row['body_east_x_m'] = body
        row['body_interval_m'] = body
        row['source_sha256'] = hashlib.sha256(f'{kind}:{frame}'.encode()).hexdigest()
        row['body_footprint_source_sha256'] = hashlib.sha256(
            f'{kind}:{frame}:{body}'.encode()).hexdigest()
        history.append(row)
        mapping.append({'frame': frame, 'time_s': time_s, 'video_frame': index})
        x = 20.0 * min(index, 799) / 799
        trace.append({'frame': frame, 'time_s': time_s, 'position_m': [x, 0.0]})
    write(destination / 'frame_map.json', {'frames': mapping})
    for name, rows in [('history.jsonl', history), ('trace.jsonl', trace)]:
        (destination / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                                 for row in rows))
    if kind == 'missing_evidence':
        (destination / 'history.jsonl').unlink()
    write(destination / 'provenance.json', {'diagnostic_fixture': True,
                                           'physical_acceptance_claimed': False,
                                           'case_id': case_id, 'kind': kind})


def assess(case_id: str, kind: str, directory: Path) -> dict:
    directory = Path(directory)
    paths = {name: directory / name for name in
             ('site.json', 'frame_map.json', 'history.jsonl', 'trace.jsonl', 'provenance.json')}
    available = {name: sha(path) for name, path in paths.items() if path.is_file()}
    status = 'unverified'
    details = {'missing': [name for name, path in paths.items() if not path.is_file()]}
    observed = {}
    if all(path.is_file() for path in paths.values()):
        site = json.loads(paths['site.json'].read_text())
        mapping = json.loads(paths['frame_map.json'].read_text())['frames']
        history = [json.loads(line) for line in paths['history.jsonl'].read_text().splitlines()]
        trace = [json.loads(line) for line in paths['trace.jsonl'].read_text().splitlines()]
        if len(mapping) != len(history) or len(trace) != len(history) or len(history) != 900:
            raise ValueError('diagnostic original source count changed')
        for index, (frame, row, motion) in enumerate(zip(mapping, history, trace)):
            if (frame['frame'] != 1000 + index or row['original_frame'] != frame['frame'] or
                    motion['frame'] != frame['frame'] or frame['time_s'] != index / 20 or
                    row['time_s'] != frame['time_s'] or motion['time_s'] != frame['time_s']):
                raise ValueError('diagnostic original source frame join changed')
        case = next(item for item in CASES if case_id.endswith('__' + item.id))
        hold = history[-100:]
        lo, hi = site['posted_interval_m']
        inside = [min(row['body_east_x_m'], hi) > max(row['body_west_x_m'], lo)
                  for row in hold]
        if case.sweep_kind == 'posted_offset':
            actual = [(row['body_west_x_m'] + row['body_east_x_m']) / 2 - hi
                      for row in hold]
            region_met = all(abs(value - case.sweep_setpoint_m) <= .25 for value in actual)
        elif case.sweep_kind == 'conflict_gap':
            actual = [row['actual_actor_body_gap_m'] for row in hold]
            region_met = all(abs(value - case.sweep_setpoint_m) <= .25 for value in actual)
        else:
            region_met = all(inside) if case.target_region == 'inside' else not any(inside)
        activity = {'park': 'parked', 'stand': 'standing', 'stop': 'stopped'}[case.activity]
        state_met = all(row['activity_observation'] == activity and
                        row['attended_observation'] is case.attended and
                        row['exception_kind'] == case.exception for row in hold)
        points = [row['position_m'] for row in trace]
        progress = math.dist(points[0], points[-1])
        moved = progress >= 1.0
        status = 'met' if region_met and state_met and moved else 'not_met'
        details = {'engineering_progress_minimum_m': 1.0,
                   'observed_progress_m': progress, 'region_met': region_met,
                   'state_met': state_met, 'hold_frames': len(hold),
                   'hold_overlap_frames': sum(inside),
                   'not_a_legal_threshold': True}
        observed = {'original_frame_count': len(history),
                    'original_progress_m': progress,
                    'hold_overlap_frames': sum(inside),
                    'requested_region': case.target_region}
    if kind == 'complete_motion' and status != 'met':
        raise ValueError('positive synthetic maneuver fixture did not complete')
    if kind == 'incomplete_motion' and status != 'not_met':
        raise ValueError('incomplete synthetic maneuver fixture unexpectedly completed')
    if kind == 'missing_evidence' and status != 'unverified':
        raise ValueError('missing-source synthetic maneuver fixture was classified')
    return {'case_id': case_id, 'diagnostic_fixture': True,
            'provenance_kind': 'synthetic_fixture', 'physical_acceptance_claimed': False,
            'legal_judgment': None, 'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {
                'status': status, 'method': 'original frame, curb target, hold state and trace progress',
                'sources': available, 'details': details,
                'legal_verdict_claimed': False}},
            'realized_observables': observed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'),
                        required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    source(args.case, args.kind, args.source)
    write(args.result, assess(args.case, args.kind, args.source))
    print('physical diagnostic', args.case, args.kind,
          json.loads(args.result.read_text())['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
