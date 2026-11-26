"""Saved-only speed and lane-change finalizer using original Native samples."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

SOURCES = ('speed-lane-history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'road-context.json')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_speed_lane(path):
    return measure(path)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior saved result; choose a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    case = config['selected_case_id']
    if case != construction['case_id'] or case not in config['supported_case_ids']:
        raise ValueError('Saved finalizer exact case identity differs')
    context = json.loads((attempt/'road-context.json').read_text())
    if context.get('case_id') != case:
        raise ValueError('Original road context names another case')
    history = rows(attempt/'speed-lane-history.jsonl')
    frames = rows(attempt/'video_frames.jsonl')
    trace = rows(attempt/'trace.jsonl')
    evidence = rows(attempt/'capture/evidence.jsonl')
    if not all(len(source) == 600 for source in (history, frames, trace, evidence)):
        raise ValueError('Requires complete original speed, frame, trace and evidence sources')
    for i, (sample, frame, track, evidence_row) in enumerate(zip(history, frames, trace, evidence)):
        if (sample['video_frame'] != i or frame['video_frame'] != i or
                sample['native_frame'] != frame['native_frame'] or
                track['frame'] != frame['native_frame'] or
                evidence_row['original_frame'] != frame['native_frame'] or
                abs(sample['time_s']-frame['time_s']) > .005 or
                abs(track['time_s']-frame['time_s']) > .005):
            raise ValueError('Original speed, trace, evidence and frame join differs')
    observed = measure_speed_lane(attempt/'speed-lane-history.jsonl')
    sources = {name: sha(attempt/name) for name in SOURCES}
    channels = attempt/'channels'
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in history:
                velocity = row['velocity_xyz_mps']
                value = (velocity if name == 'kin.velocity' else
                         (sum(component*component for component in velocity)**.5)*2.2369362921
                         if name == 'kin.speed' else row['subject_id'])
                stream.write(json.dumps({'time_s':row['time_s'],'value':value})+'\n')
        recording_evidence.append({'name':name,'unit':channel['unit'],
                                   'reference':'channels/'+path.name})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'speed_observation': {
                  'method': 'measure_speed_lane', 'value': observed, 'sources': sources}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    target = config['requested_speed_mps'] * 2.2369362921
    diagnostic = context.get('review_kind') == 'synthetic_diagnostic'
    result = {
        'case_id': case, 'measured_values': observed,
        'target_checks': [{'target': 'original measured speed and lane change',
                           'requested': target,
                           'measured': observed['maximum_mph'],
                           'method': 'measure_speed_lane',
                           'tolerance': 1 if diagnostic else 0,
                           'matched': bool(diagnostic and abs(target-observed['maximum_mph']) < 1),
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved original sources processed; physical completion awaits independent review',
        'physical_failure_flags': ['Original physical speed, lane transition and pixels unreviewed'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': recording_evidence,
        'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_source_review',
        'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
