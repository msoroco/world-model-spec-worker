"""Produce the selected taxi measurement from saved sources, without legal inference."""
import argparse
import json
from pathlib import Path

from finalize_original import SOURCES, inspect, sha

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def source_join_measurement(attempt):
    attempt = Path(attempt)
    for name in ('yellow-zone-native.jsonl', 'sign-review.json',
                 'commercial-status-review.json',
                 'passenger-purpose-review.json', 'ordinary-rules-review.json',
                 'observed-passenger-activity.jsonl'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    if (attempt / 'capture-seal.json').is_file():
        kind = 'original_native'
        manifest = attempt / 'source-manifest.json'
        if not manifest.is_file():
            raise ValueError('Missing required source: source-manifest.json')
    else:
        recorder = attempt / 'capture' / 'recorder_info.txt'
        if not recorder.is_file() or 'Synthetic taxi diagnostic' not in recorder.read_text():
            raise ValueError('Unsealed acquisition is not a declared diagnostic')
        kind = 'synthetic_cpu_fixture'
        for name in ('taxicab-review.json', 'sign-review.json',
                     'commercial-status-review.json',
                     'passenger-purpose-review.json', 'ordinary-rules-review.json'):
            if json.loads((attempt / name).read_text()).get('synthetic_cpu_fixture') is not True:
                raise ValueError('Unsealed diagnostic review differs: ' + name)
        manifest = attempt / 'source-manifest.json'
        if manifest.exists():
            raise ValueError('Unsealed diagnostic source manifest already exists')
        manifest.write_text(json.dumps({'source_kind': kind,
            'sha256': {name: sha(attempt / name) for name in SOURCES}}, indent=2) + '\n')
    measured = inspect(attempt, manifest, kind)
    measured.pop('legal_verdict', None)
    return measured


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Fresh selected taxi analysis required')
    construction = json.loads((attempt / 'construction.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    case = config.get('selected_case_id')
    if case != construction.get('case_id') or case != config.get('case_id'):
        raise ValueError('Selected taxi case identity differs')
    measured = source_join_measurement(attempt)
    if measured['case_id'] != case:
        raise ValueError('Measured taxi case identity differs')
    sources = {name: sha(attempt / name) for name in
               ('yellow-zone-native.jsonl', 'sign-review.json',
                'commercial-status-review.json',
                'passenger-purpose-review.json', 'ordinary-rules-review.json',
                'observed-passenger-activity.jsonl')}
    expected = 0 if case.endswith('__probe_b') else 600
    channels = construction['recording_description']['channels']
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    native = [json.loads(line) for line in
              (attempt / 'yellow-zone-native.jsonl').read_text().splitlines()]
    activity_path = attempt / 'observed-passenger-activity.jsonl'
    if not activity_path.is_file():
        raise ValueError('Missing required source: observed-passenger-activity.jsonl')
    activity = [json.loads(line) for line in activity_path.read_text().splitlines()]
    if len(activity) != 600 or any(
            row.get('video_frame') != index or
            row.get('native_frame') != native[index]['native_frame'] or
            row.get('source_kind') != measured['source_kind']
            for index, row in enumerate(activity)):
        raise ValueError('Original passenger activity frame join differs')
    sign = json.loads((attempt / 'sign-review.json').read_text())
    taxi = json.loads((attempt / 'taxicab-review.json').read_text())
    commercial = json.loads((attempt / 'commercial-status-review.json').read_text())
    if not sign.get('observed_sign_content'):
        raise ValueError('Missing source-observed sign content')
    observed = []
    for channel in channels:
        name = channel['name']
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('x') as stream:
            for row, action in zip(native, activity):
                value = (row['civil_time_local'] if name == 'env.civil_time'
                         else row['time_s'] if name == 'kin.time'
                         else row['taxi_velocity_xyz_mps'] if name == 'drv.standing_or_parked'
                         else action['observed_door_open'] if name == 'sig.door_open'
                         else action['observed_occupant_count'] if name == 'ru.occupant_count'
                         else taxi['observed_taxicab'] if name == 'ru.taxicab'
                         else {'actor_id': commercial['taxi_actor_id'],
                               'classification_review': commercial.get('observed_commercial_use'),
                               'source_basis': commercial['source_basis']}
                              if name == 'ru.commercial_motor_vehicle'
                         else sign['observed_curb_color'] if name == 'st.curb_zone'
                         else sign['observed_sign_content'] if name == 'dev.regulatory_sign'
                         else row['civil_time_local'][11:16] < '17:00' and
                              row['civil_time_local'][11:16] >= '09:00')
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        observed.append({'name': name, 'unit': channel['unit'],
                         'reference': reference})
    report = {'format': 'worker-analysis-report', 'case_id': case,
        'measurements': {'taxi_yellow_zone_measurement': {
            'method': 'source_join_measurement', 'value': measured, 'sources': sources}},
        'source_complete': True, 'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measured,
        'target_checks': [{'target': 'posted-hour stopped taxi body frames',
            'requested': expected, 'measured': measured['posted_active_stopped_frames'],
            'method': 'source_join_measurement', 'tolerance': 0,
            'matched': measured['posted_active_stopped_frames'] == expected,
            'physical_cause_confirmed': False,
            'cause_evidence': list(sources)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved taxi source measurement; physical and legal review pending',
        'physical_failure_flags': ['Original authority and physical completion unconfirmed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': observed, 'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if not measured['original_native_observed']
                           else 'original_source_review', 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
