"""Saved-only signal approach measurement; no legal or physical verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from signal_approach import measure

SOURCES = ('signal_raw.json', 'context-survey.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_signal_approach(raw):
    return measure(raw)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    case = config.get('selected_case_id')
    if case != construction.get('case_id') or case not in config.get('supported_case_ids', []):
        raise ValueError('Saved finalizer exact-case identity differs')
    raw = json.loads((attempt/'signal_raw.json').read_text())
    survey = json.loads((attempt/'context-survey.json').read_text())
    if survey.get('case_id') != case or survey.get('review_kind') not in (
            'synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Signal and exception survey source identity differs')
    if set(raw.get('context_sources', {}).values()) != {'context-survey.json'}:
        raise ValueError('Raw context sources do not bind original survey')
    observed = measure_signal_approach(raw)
    observed_without_verdict = {key: value for key, value in observed.items()
                                if key != 'legal_verdict'}
    frames = [json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt/'trace.jsonl').read_text().splitlines()]
    if len(frames) != 600 or len(trace) != 600 or len(observed['frames']) != 600:
        raise ValueError('Requires full original trace/frame join')
    for index, (frame, row, motion) in enumerate(zip(frames, trace, raw['frames'])):
        if (frame['video_frame'] != index or row['frame'] != frame['carla_frame'] or
                motion['native_frame'] != frame['carla_frame'] or
                abs(frame['time_s']-row['time_s']) > 1e-6 or
                abs(frame['time_s']-motion['time_s']) > 1e-6):
            raise ValueError('Signal trace and original camera frame join differs')
    source_hashes = {name: sha(attempt/name) for name in SOURCES}
    values = {
        'stopping_context': {'method': 'measure_signal_approach',
                             'value': {'stationary_sample_count': observed['stationary_sample_count'],
                                       'halt_purpose_source': survey.get('halt_purpose')},
                             'sources': source_hashes},
        'signal_approach_distance': {'method': 'measure_signal_approach',
                                     'value': observed_without_verdict, 'sources': source_hashes},
        'official_signal_context': {'method': 'measure_signal_approach',
                                    'value': {'native_signal_actor_id': raw['signal'].get('actor_id'),
                                              'governs_lane_native': raw['signal'].get('governs_lane'),
                                              'official_status_source': survey.get('official_signal_status'),
                                              'highway_status_source': survey.get('highway_status')},
                                    'sources': source_hashes},
        'exception_context': {'method': 'measure_signal_approach',
                              'value': {'traffic_conflict_source': survey.get('other_traffic_conflict'),
                                        'law_direction_source': survey.get('applicable_law_direction'),
                                        'officer_direction_source': survey.get('officer_direction'),
                                        'device_direction_source': survey.get('device_direction')},
                              'sources': source_hashes},
    }
    diagnostic = survey['review_kind'] == 'synthetic_diagnostic'
    channels = attempt/'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for measured in observed['frames']:
                value = (measured['speed_mps'] if name == 'kin.speed' else
                         measured['centre_to_signal_station_m'] if name == 'rel.centre_distance' else
                         measured['approach_side_geometry'] if name == 'drv.approaching' else
                         measured['speed_mps'] <= .15 if name == 'drv.standing_or_parked' else
                         raw['signal'].get('actor_id') if name == 'dev.traffic_signal' else
                         raw['signal']['roadside_position'] if name == 'dev.position' else
                         measured['front_edge_to_signal_station_m'] if name == 'rel.occupies' else
                         {'source': 'context-survey.json',
                          'observed': survey.get('other_traffic_conflict'),
                          'review_kind': survey['review_kind']}
                         if name == 'drv.forced_halt' else
                         {'source': 'context-survey.json',
                          'observed': survey.get('officer_direction'),
                          'review_kind': survey['review_kind']}
                         if name == 'dev.human_direction' else
                         {'front_edge_to_signal_station_m': measured['front_edge_to_signal_station_m'],
                          'centre_to_signal_station_m': measured['centre_to_signal_station_m'],
                          'rear_edge_to_signal_station_m': measured['rear_edge_to_signal_station_m']}
                         if name == 'stop_distance_on_signal_approach' else
                         raw['frames'][measured['frame_index']]['vehicle_footprint_xy_m'])
                stream.write(json.dumps({'time_s': measured['time_s'], 'value': value})+'\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/'+path.name})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': values, 'source_complete': True,
              'diagnostic_fixture': diagnostic, 'physical_or_legal_acceptance': False}
    observed_gap_m = observed['frames'][-1]['front_edge_to_signal_station_m']
    requested_gap_m = float(config['requested_front_gap_ft'])*.3048
    final_samples = observed['frames'][-100:]
    rest_samples = [sample for sample in final_samples
                    if sample['speed_mps'] <= .15]
    sustained_requested_halt = (len(rest_samples) >= 80 and
        all(abs(sample['front_edge_to_signal_station_m']-requested_gap_m) <= .2
            for sample in rest_samples))
    original = not diagnostic
    physical_sources = {name: source_hashes[name] for name in
                        ('signal_raw.json', 'trace.jsonl', 'video_frames.jsonl', 'road.xodr')}
    physical_checks = {
        'setup': {'status': 'met' if original else 'unverified',
                  'method': 'full 600-frame signal, lane, pose and time join',
                  'sources': physical_sources},
        'maneuver': {'status': ('met' if sustained_requested_halt else 'not_met')
                     if original else 'unverified',
                     'method': 'at least 80 of final 100 original samples at rest and within engineering requested gap window',
                     'sources': physical_sources,
                     'observed_final_rest_samples': len(rest_samples),
                     'requested_gap_m': requested_gap_m,
                     'observed_final_gap_m': observed_gap_m}}
    result = {'case_id': case, 'measured_values': observed_without_verdict,
              'target_checks': [{'target': 'observed signal approach stopping gap',
                                 'requested': requested_gap_m, 'measured': observed_gap_m,
                                 'method': 'measure_signal_approach',
                                 'tolerance': .2, 'matched': abs(observed_gap_m-requested_gap_m) <= .2,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': original, 'behavior_attempted': original,
              'maneuver_completed': original and sustained_requested_halt,
              'physical_checks': physical_checks,
              'termination_reason': 'Saved source measured; original halt purpose and official status require independent review',
              'physical_failure_flags': ['Original signal, halt cause, camera pixels and exception status unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
