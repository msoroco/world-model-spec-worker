"""Saved alley-entry diagnostic; never certifies a statutory exception."""
import argparse
import json
from pathlib import Path
import shutil

from finalize import verify_original_joins, video_frames, sha
from measure_alley_transition import measure


def alley_transition_observation(attempt):
    attempt = Path(attempt)
    for name in ('native_samples.jsonl','road_geometry.json','alley-transition-sources.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    transition = measure(attempt)
    return {'method':'alley_transition_observation',
            'value':transition,
            'sources':{**transition['source_sha256'],
                       'alley-transition-sources.json':sha(attempt/'alley-transition-sources.json')}}


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads((attempt/'config.json').read_text())
    if config['case_suffix'] != 'probe_c_alley_entry' or config['duration_s'] != 24 or config['rate_hz'] != 20:
        raise ValueError('Wrong exact alley case or capture timing')
    original = verify_original_joins(attempt, 480)
    observation = alley_transition_observation(attempt)
    transition = observation['value']
    videos = [name+'.mkv' for name in
              ('overview', 'approach', 'reference_corner', 'driver_reference')]
    counts = {name: video_frames(attempt/name) for name in videos}
    if any(count != 480 for count in counts.values()):
        raise ValueError('Original alley source video frame count differs')
    if not (attempt/'channels').is_dir():
        source_channels = attempt/'source_channels'
        if not source_channels.is_dir():
            raise ValueError('Missing required source: source_channels')
        for channel in config['recording_description']['channels']:
            if not (source_channels/(channel['name']+'.jsonl')).is_file():
                raise ValueError('Missing required source: source_channels/'+channel['name']+'.jsonl')
        shutil.copytree(source_channels,attempt/'channels')
    evidence = []
    for channel in config['recording_description']['channels']:
        reference = 'channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        evidence.append({'name': channel['name'], 'unit': channel['unit'],
                         'reference': reference})
    for context in config['recording_description']['context_inputs']:
        reference = ('exception_context.json' if context['name'] == 'requested_exception_context'
                     else 'context.json')
        if not (attempt/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        evidence.append({'name': context['name'], 'unit': context['unit'],
                         'reference': reference})
    measured = transition['time_bounded_geometry_candidate']
    result = {'case_id': config['case_id'],
        'measured_values': {
            'first_facility_entry_native_frame': transition['first_facility_entry_native_frame'],
            'first_alley_footprint_native_frame': transition['first_alley_footprint_native_frame'],
            'facility_to_alley_gap_s': transition['facility_to_alley_gap_s'],
            'simultaneous_moving_overlap_frames': transition['simultaneous_moving_overlap_frames']},
        'target_checks': [{'target': 'moving full-body facility entry followed by alley overlap',
            'requested': True, 'measured': measured,
            'method': 'source-hashed original-frame body polygon and authored facility/alley bounds',
            'tolerance': '0 to 2 s entry-to-alley gap with simultaneous moving body overlap',
            'matched': measured, 'physical_cause_confirmed': False,
            'cause_evidence': ['native_samples.jsonl', 'road_geometry.json',
                               'alley-transition-sources.json']}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': measured,
        'termination_reason': 'full source duration retained',
        'physical_failure_flags': ['Native route identity, designation, statutory exception and pixels unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'alley_transition_geometry': {
            'value': transition['simultaneous_moving_overlap_frames'], 'unit': 'frames',
            'method': 'source-bound moving body overlap with facility and alley polygons',
        'time_window': 'entire 480-frame source attempt', 'statistic': 'count',
            'reference': 'native_samples.jsonl', 'sample_window_s': [0.05, 24.0]}},
        'provenance_kind': 'native', 'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c10052-alley-saved-diagnostic-v1',
        'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
        'measurements': {'alley_transition_observation': observation},
        'original_joins': original, 'video_frames': counts,
        'source_sha256': {'native_samples.jsonl': sha(attempt/'native_samples.jsonl'),
            'road_geometry.json': sha(attempt/'road_geometry.json')},
        'scope': ('synthetic saved CPU diagnostic' if transition['source_kind']=='synthetic_cpu_fixture'
                  else 'original Native saved diagnostic')+
            '; no statutory exception verdict or acceptance'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
