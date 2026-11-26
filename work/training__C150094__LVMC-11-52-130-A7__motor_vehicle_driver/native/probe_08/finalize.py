"""Finalize saved driveway sources without inferring a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_driveway import CAMERAS, COUNT, measure


def driveway_observation(attempt):
    """Return source joined driveway measurements for the selected requirement."""
    return measure(attempt)


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Choose a fresh recorded-only attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('frames') != COUNT:
        raise ValueError('Driveway capture profile differs')
    names = ('driveway_context.json', 'native_parking_trace.jsonl',
             'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
             'capture/native/frames.jsonl', 'road.xodr') + tuple(
                 name + '.mkv' for name in CAMERAS)
    hashes = {name: digest(required(attempt, name)) for name in names}
    observation = driveway_observation(attempt)
    provenance = provenance_record(attempt)
    original = observation['review_kind'] == 'original_source_review'
    if original != (provenance['provenance_kind'] == 'native' and
                    not provenance['diagnostic_fixture']):
        raise ValueError('Driveway source and acquisition provenance disagree')
    frame_map = rows(attempt / 'video_frames.jsonl')
    parking = rows(attempt / 'native_parking_trace.jsonl')
    core = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    native = rows(attempt / 'capture/native/frames.jsonl')
    if any(len(v) != COUNT for v in (frame_map, parking, core, evidence, native)):
        raise ValueError('Incomplete driveway source/Core frame join')
    for index, (f, p, c, e, n) in enumerate(zip(frame_map, parking, core, evidence, native)):
        frame = f.get('native_frame')
        if (f.get('video_frame') != index or p.get('video_frame') != index or
                p.get('native_frame') != frame or c.get('frame') != frame or
                e.get('original_frame') != frame or n.get('frame') != frame or
                abs(c.get('time_s', -100) - f['time_s']) > 1e-5 or
                abs(e.get('recording_time_s', -100) - f['time_s']) > 1e-5 or
                abs(n.get('time_s', -100) - f['time_s']) > 1e-5 or
                abs(c.get('speed_mps', -100) - p['ego_speed_mps']) > 1e-4 or
                abs(e.get('ego', {}).get('speed_mps', -100) - p['ego_speed_mps']) > 1e-4):
            raise ValueError('Original driveway/Core source join differs')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    channel_names = [c['name'] for c in config['recording_description']['channels']]
    context = json.loads((attempt / 'driveway_context.json').read_text())
    bounds = context['driveway_curb_interval_m']
    for name in channel_names:
        stream = []
        for frame, row in zip(frame_map, parking):
            low = row['ego_curb_station_m'] - row['ego_half_length_m']
            high = row['ego_curb_station_m'] + row['ego_half_length_m']
            values = {
                'st.driveway_or_alley_entrance': {'kind': context['driveway_kind'], 'curb_interval_m': bounds},
                'rel.centre_distance': max(bounds[0] - high, low - bounds[1], 0.0),
                'drv.standing_or_parked': {'speed_mps': row['ego_speed_mps'], 'park_brake_engaged': row['park_brake_engaged']},
                'rel.occupies': low <= bounds[1] and high >= bounds[0],
                'kin.extent': {'curb_low_m': low, 'curb_high_m': high},
                'ru.official_vehicle': {'usps_vehicle': context['usps_vehicle'], 'official_business': context['usps_official_business']},
                'dev.regulatory_sign': {'officer_direction': context['officer_direction'], 'traffic_device_direction': context['traffic_device_direction']},
            }
            stream.append({'time_s': frame['time_s'], 'value': values[name]})
        (channel_dir / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in stream))
    (channel_dir / 'driveway_context.json').write_text(json.dumps({'driveway_context': context}, allow_nan=False) + '\n')
    result = {
        'case_id': config['case_id'], 'measured_values': observation,
        'target_checks': [{'target': 'driveway_footprint_distance',
                           'requested': config.get('target_gap_m'),
                           'measured': observation['minimum_footprint_gap_m_at_rest'],
                           'method': 'Native body footprint against reviewed curb opening',
                           'tolerance': 0.25, 'matched': config.get('target_gap_m') is not None and abs(observation['minimum_footprint_gap_m_at_rest'] - config['target_gap_m']) <= 0.25,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native_parking_trace.jsonl',
                                              'driveway_context.json']}],
        'setup_confirmed': original,
        'behavior_attempted': original and bool(observation['rest_frame_count']),
        'maneuver_completed': original and bool(observation['rest_frame_count']),
        'termination_reason': '600 source frames retained',
        'physical_failure_flags': ['independent_driveway_authority_and_pixels_require_review'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': ([{'name': name, 'unit': 'structured',
                                 'reference': 'channels/' + name + '.jsonl'}
                                for name in channel_names] +
                               [{'name': 'driveway_context', 'unit': 'structured',
                                 'reference': 'channels/driveway_context.json'}]),
        'realized_observables': {'minimum_footprint_gap_m_at_rest': {
            'value': observation['minimum_footprint_gap_m_at_rest'], 'unit': 'm',
            'method': 'source-bound Native body footprint and reviewed curb opening',
            'time_window': '600 frames', 'statistic': 'minimum',
            'reference': 'native_parking_trace.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c150094-driveway-analysis-v1', 'case_id': config['case_id'],
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'measurements': {'driveway_observation': {
                  'method': 'driveway_observation', 'value': observation,
                  'sources': hashes}}, 'source_hashes': hashes,
              'provenance': provenance,
              'limitations': ['Synthetic fixture does not establish original Native parking, driveway authority, pixels or physical acceptance.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
