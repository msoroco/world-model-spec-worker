"""Recorded-only software analysis of the two-actor synthetic diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_yield import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_priority_requirement(observed):
    return {'value': observed, 'method': 'measure_priority_requirement',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}


def measure_prior_yield_antecedent(observed):
    value = {'prior_stopped_frames': observed['entrant_prior_stopped_frames'],
             'about_to_enter_first_frame': observed['about_to_enter_first_frame'],
             'lawful_prior_yield_verified': False}
    return {'value': value, 'method': 'measure_prior_yield_antecedent',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}


def measure_entrant_entry_phase(observed, rows):
    crossing = [i for i, row in enumerate(rows) if -7 <= row['entrant']['x_m'] <= 7]
    if not crossing or crossing != list(range(min(crossing), max(crossing) + 1)):
        raise ValueError('Contiguous entrant crossing source absent')
    value = {'about_to_enter_first_frame': observed['about_to_enter_first_frame'],
             'crossing_first_frame': crossing[0], 'crossing_last_frame': crossing[-1],
             'crossing_observed': True, 'physical_or_legal_timing_verified': False}
    return {'value': value, 'method': 'measure_entrant_entry_phase',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}


def frames(path):
    if not path.is_file():
        raise ValueError('Missing original source camera: ' + path.name)
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=nb_read_frames', '-of',
                          'default=noprint_wrappers=1:nokey=1', str(path)],
                         capture_output=True, text=True, check=True, timeout=120)
    if not run.stdout.strip().isdigit():
        raise ValueError('Original camera decode failed: ' + path.name)
    return int(run.stdout.strip())


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain previous finalization; use fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case_id']
    if not case.startswith('training__C111294__LVMC-11-12-070-B__motor_vehicle_driver__probe_'):
        raise ValueError('Exact case differs')
    observed = measure(attempt, case)
    native = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(mapping) != 600 or any(m.get('native_frame') != n['native_frame'] or
                                  m.get('time_s') != n['time_s'] or
                                  m.get('video_frame') != i
                                  for i, (m, n) in enumerate(zip(mapping, native))):
        raise ValueError('Original frame mapping differs')
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Derived channel directory preexists')
    channels.mkdir()
    values = {'through_body_pose': lambda n, m: n['through'],
              'entrant_body_pose': lambda n, m: n['entrant'],
              'frame_join': lambda n, m: m}
    if set(values) != {c['name'] for c in config['recording_description']['channels']}:
        raise ValueError('Recording channel declaration differs')
    for name, value in values.items():
        path = channels / (name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': m['time_s'],
                                            'native_frame': m['native_frame'],
                                            'value': value(n, m)}, allow_nan=False) + '\n'
                                for n, m in zip(native, mapping)))
    camera_counts = {name + '.mkv': frames(attempt / (name + '.mkv')) for name in CAMERAS}
    if set(camera_counts.values()) != {600}:
        raise ValueError('Four original source cameras need exactly 600 frames')
    expected = case.endswith('probe_1')
    matched = observed['through_yield_response_observed'] == expected
    observed_record = {key: value for key, value in observed.items() if key != 'legal_verdict'}
    source_kind = observed['source_kind']
    native_observed = source_kind == 'native_observation'
    result = {
        'case_id': case,
        'measured_values': {'priority_sequence': observed_record},
        'target_checks': [{'target': 'through vehicle yield response after entrant prior stop',
                           'requested': expected, 'measured': observed['through_yield_response_observed'],
                           'method': 'joined original 600-frame two-actor speed and position',
                           'tolerance': 0, 'matched': matched,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native_samples.jsonl', 'road.xodr']}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': ('Original Native sequence measured; physical review pending'
                               if native_observed else
                               'Synthetic saved software sequence measured; physical review pending'),
        'physical_failure_flags': ['through_highway_designation_and_lawful_prior_yield_unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                'reference': 'channels/' + c['name'] + '.jsonl'}
                               for c in config['recording_description']['channels']],
        'realized_observables': {
            'entrant_prior_stopped_frames': {'value': observed['entrant_prior_stopped_frames'],
                                             'unit': 'count', 'method': 'source-joined stopped-frame count',
                                             'time_window': 'entire recorded interval',
                                             'statistic': 'count', 'reference': 'native_samples.jsonl'}},
        'provenance_kind': source_kind, 'accepted': False,
        'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111294-saved-analysis-v1', 'case_id': case,
              'measurements': {'priority_requirement': measure_priority_requirement(observed),
                               'prior_yield_antecedent': measure_prior_yield_antecedent(observed),
                               'entrant_entry_phase': measure_entrant_entry_phase(observed, native)},
              'observed': observed, 'video_frame_counts': camera_counts,
              'derived_channel_sha256': {name: sha(channels / (name + '.jsonl')) for name in values},
              'original_source_sha256': {name: sha(attempt / name) for name in
                                         ('native_samples.jsonl', 'diagnostic-source-manifest.json',
                                          'road.xodr', 'video_frames.jsonl', 'trace.jsonl')},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
