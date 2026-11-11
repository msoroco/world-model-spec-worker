"""Saved-only C10364 original-source measurement; no legal verdict."""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from alley_measurement import measure


PREFIX = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__'
SUFFIXES = {f'{interest}_{speed}mps' for interest in ('person', 'property')
            for speed in (3, 5, 7)}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def measure_alley(attempt):
    """Named selected measurement entrypoint for the exact source contract."""
    root = Path(attempt)
    for name in ('participant_footprints.jsonl', 'ego_motion.jsonl',
                 'trace.jsonl', 'video_frames.jsonl'):
        path = root / name
        if not path.is_file() or not path.read_bytes():
            raise ValueError('Missing required source: ' + name)
    return measure(root)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def selected_config(root):
    config = json.loads((root / 'config.json').read_text())
    case = config.get('selected_case_id', '')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1b', 'C10364', 'motor_vehicle_driver') or (
            not case.startswith(PREFIX) or case[len(PREFIX):] not in SUFFIXES):
        raise ValueError('Wrong exact alley finalizer identity')
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected alley recording description missing')
    return config, case, description


def analyze(attempt):
    root = Path(attempt)
    _, case, _ = selected_config(root)
    observed = measure_alley(root)
    return {'format': 'worker-analysis-report', 'case_id': case,
            'measurements': {'alley_original_exposure': {
                'method': 'measure_alley', 'value': observed,
                'sources': observed['source_sha256']}},
            'limitations': observed['limitations'] + [
                'Original geometry and motion do not establish camera visibility or legal endangerment.'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def assess_passage(attempt):
    source = Path(attempt) / 'participant_footprints.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError('Alley passage needs consecutive original body rows')

    def center(corners):
        return [sum(point[axis] for point in corners) / len(corners)
                for axis in (0, 1)]

    first, last = center(rows[0]['ego_corners']), center(rows[-1]['ego_corners'])
    dx, dy = last[0] - first[0], last[1] - first[1]
    displacement = hypot(dx, dy)
    direction = (dx / displacement, dy / displacement) if displacement >= 1.0 else None
    detail = {'subject_displacement_m': displacement}
    for kind, key in (('pedestrian', 'pedestrian_corners'),
                      ('property', 'property_corners')):
        if direction is None:
            detail[kind + '_passage_observed'] = False
            continue
        before = center(rows[0][key]); after = center(rows[-1][key])
        initial = sum((before[a] - first[a]) * direction[a] for a in (0, 1))
        final = sum((after[a] - last[a]) * direction[a] for a in (0, 1))
        detail[kind + '_ahead_initial_m'] = initial
        detail[kind + '_ahead_final_m'] = final
        detail[kind + '_passage_observed'] = initial > 0 and final < 0
    return {'status': 'met' if any(detail.get(k + '_passage_observed')
                                 for k in ('pedestrian', 'property')) else 'not_met',
            'method': 'Original body-center travel and before/after participant passage',
            'sources': {source.name: digest(source)},
            'intervals': [{'first_frame': rows[0]['frame'], 'last_frame': rows[-1]['frame'],
                           'first_time_s': rows[0]['time_s'],
                           'last_time_s': rows[-1]['time_s']}],
            'details': detail, 'legal_verdict_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config, case, description = selected_config(root)
    observed = report['measurements']['alley_original_exposure']['value']
    frames = observed['observations']
    footprint_source = root / 'participant_footprints.jsonl'
    footprint_rows = [json.loads(line) for line in footprint_source.read_text().splitlines() if line.strip()]
    footprint_channel = root / 'participant_footprints_channel.jsonl'
    if footprint_channel.exists():
        raise ValueError('Retain prior derived alley channel')
    footprint_channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': {'ego_id': row['ego_id'], 'pedestrian_id': row['pedestrian_id'],
                  'property_id': row['property_id'],
                  'ego_corners': row['ego_corners'],
                  'pedestrian_corners': row['pedestrian_corners'],
                  'property_corners': row['property_corners']}}) + '\n'
        for row in footprint_rows))
    evidence = [{'name': 'participant_footprints', 'unit': 'structured record',
                 'reference': footprint_channel.name,
                 'sha256': digest(footprint_channel)}]
    observables = {}
    for kind, key in (('pedestrian', 'pedestrian_surface_gap_m'),
                      ('property', 'property_surface_gap_m')):
        name = kind + '_gap_m'
        channel = root / (name + '.jsonl')
        if channel.exists():
            raise ValueError('Retain prior derived alley channel')
        channel.write_text(''.join(json.dumps({'frame': row['frame'],
            'time_s': row['time_s'], 'value': row[key]}) + '\n' for row in frames))
        evidence.append({'name': name, 'unit': 'm', 'reference': channel.name,
                         'sha256': digest(channel)})
        observables[name] = {'unit': 'm',
            'method': 'original Native body polygon distance',
            'time_window': 'all original frames', 'statistic': 'min',
            'reference': channel.name,
            'value': min(row[key] for row in frames),
            'sample_window_s': [frames[0]['time_s'], frames[-1]['time_s']]}
    from worker_exchange.native_output import physical_result
    selected = 'pedestrian' if case[len(PREFIX):].startswith('person_') else 'property'
    result = {'case_id': case,
        'measured_values': {'alley_original_exposure': observed},
        'target_checks': [{'target': 'measured original ' + selected + ' exposure',
            'requested': 'retained subject/person/property body motion',
            'measured': observables[selected + '_gap_m']['value'],
            'method': 'original Native polygon surface gap',
            'tolerance': None, 'matched': False,
            'physical_cause_confirmed': False,
            'cause_evidence': 'Original sources joined; physical review pending'}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved alley measurement complete; physical outcome unverified',
        'physical_failure_flags': {'detection_validated': False},
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence,
        'realized_observables': observables,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False}
    result = physical_result(root, result)
    result['realized_observables'].update(observables)
    passage = assess_passage(root)
    result['physical_checks']['maneuver'] = passage
    result['maneuver_completed'] = passage['status'] == 'met'
    result['termination_reason'] = ('Saved alley measurement complete; original passage '
                                    + passage['status'] + '; legal judgment separate')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior alley analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
