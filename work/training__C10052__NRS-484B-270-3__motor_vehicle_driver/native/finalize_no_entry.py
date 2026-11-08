"""Finalize a source-bound straight-through facility-entry control."""
import argparse
import json
from pathlib import Path
import shutil

from finalize import verify_original_joins, video_frames, sha
from measure_entry import measure


def entry_observation(attempt):
    attempt = Path(attempt)
    for name in ('native_samples.jsonl','road_geometry.json','entry-sources.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    entry = measure(attempt)
    return {'method':'moving_body_facility_entry',
            'value':entry,
            'sources':{**entry['source_sha256'],
                       'entry-sources.json':sha(attempt/'entry-sources.json')}}


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads((attempt/'config.json').read_text())
    if config['case_suffix'] != 'probe_d_no_entry' or config['duration_s'] != 24 or config['rate_hz'] != 20:
        raise ValueError('Wrong exact no-entry case or capture timing')
    original = verify_original_joins(attempt, 480)
    observation = entry_observation(attempt)
    entry = observation['value']
    videos = [name+'.mkv' for name in
              ('overview', 'approach', 'reference_corner', 'driver_reference')]
    counts = {name: video_frames(attempt/name) for name in videos}
    if any(count != 480 for count in counts.values()):
        raise ValueError('Original no-entry source video frame count differs')
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
    samples=[json.loads(line) for line in (attempt/'native_samples.jsonl').read_text().splitlines() if line.strip()]
    traversed=samples[0]['native_center_xy_m'][0] < -40 and samples[-1]['native_center_xy_m'][0] > 10
    no_entry=traversed and entry['moving_occupied_frames']==0 and not entry['moving_entry_measured']
    result = {'case_id': config['case_id'],
        'measured_values': {
            'moving_entry_measured': entry['moving_entry_measured'],
            'moving_occupied_frames': entry['moving_occupied_frames'],
            'straight_route_traversed': traversed},
        'target_checks': [{'target': 'straight-through control with no moving full-body facility entry',
            'requested': True, 'measured': no_entry,
            'method': 'source-hashed original-frame body polygon and authored facility bounds',
            'tolerance': 'zero moving occupied frames over 480 frames and x crossing -40 to +10 m',
            'matched': no_entry, 'physical_cause_confirmed': False,
            'cause_evidence': ['native_samples.jsonl', 'road_geometry.json',
                               'entry-sources.json']}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': no_entry,
        'termination_reason': 'full source duration retained',
        'physical_failure_flags': ['Native route identity, designation, statutory exception and pixels unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'moving_facility_occupancy': {
            'value': entry['moving_occupied_frames'], 'unit': 'frames',
            'method': 'source-bound moving body overlap with facility polygon',
        'time_window': 'entire 480-frame source attempt', 'statistic': 'count',
            'reference': 'native_samples.jsonl', 'sample_window_s': [0.05, 24.0]}},
        'provenance_kind': 'native', 'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c10052-no-entry-saved-diagnostic-v1',
        'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
        'measurements': {'moving_body_facility_entry': observation},
        'original_joins': original, 'video_frames': counts,
        'source_sha256': {'native_samples.jsonl': sha(attempt/'native_samples.jsonl'),
            'road_geometry.json': sha(attempt/'road_geometry.json')},
        'scope': ('synthetic saved CPU diagnostic' if entry['source_kind']=='synthetic_cpu_fixture'
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
