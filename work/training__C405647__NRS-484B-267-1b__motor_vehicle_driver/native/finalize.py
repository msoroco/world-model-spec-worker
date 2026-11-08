"""Finalize saved 1(b) evidence for the portable worker contract.

This records measured geometry and source joins. Emergency authority, flashing
lamp qualification, signed shoulder permission and legal outcome remain open.
"""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import AID, measure

SOURCES = ('source-scope.json', 'actor-frames.jsonl', 'trace.jsonl', 'video_frames.jsonl')
VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'right_edge.mkv', 'rear_approach.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    scope = json.loads((attempt / 'source-scope.json').read_text())
    suffix = scope.get('case_suffix')
    case_id = AID + '__' + str(suffix)
    if (suffix not in ('reference', 'contrast') or config.get('case_id') != case_id or
            construction.get('case_id') != case_id or
            config.get('candidate_id') not in ('primary', 'fallback1', 'fallback2', 'fallback3')):
        raise ValueError('Exact case/configuration differs')
    expected_sources = scope.get('native_source_hashes', {})
    for name, expected in expected_sources.items():
        if not (attempt / name).is_file() or sha(attempt / name) != expected:
            raise ValueError('Saved Native source hash differs: ' + name)
    actor = rows(attempt / 'actor-frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    if len(actor) != len(trace) or len(trace) != len(mapping) or len(mapping) != 480:
        raise ValueError('Saved actor/trace/video frame counts differ')
    for index, (a, t, m) in enumerate(zip(actor, trace, mapping)):
        if (a.get('frame') != index or a.get('video_frame') != index or
                m.get('video_frame') != index or m.get('native_frame') != a.get('native_frame') or
                m.get('carla_frame') != a.get('native_frame') or
                t.get('frame') != a.get('native_frame') or
                abs(float(t.get('time_s', -1)) - float(m.get('time_s', -2))) > 1e-6 or
                abs(float(a.get('time_s', -1)) - index / 20) > 1e-4):
            raise ValueError('Saved actor/trace/video frame join differs')
    measurement = measure(attempt)
    requested = suffix == 'reference'
    observed = measurement['edge_before_catchup']
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for a, m in zip(actor, mapping):
                values = {
                    'subject_pose_body_speed': a['subject'],
                    'approach_pose': a['approach'],
                    'camera_frame_join': {'native_frame': m['native_frame'],
                                          'video_frame': m['video_frame']},
                }
                stream.write(json.dumps({'time_s': m['time_s'], 'value': values[name]}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    report = {'format': 'c405647-1b-saved-analysis-v1', 'case_id': case_id,
              'selected': False, 'draft_only': True,
              'measurements': {'right_edge_geometry': {
                  'method': 'measure', 'value': measurement,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = {'case_id': case_id, 'measured_values': {
                  key: value for key, value in measurement.items()
                  if key not in ('legal_immediacy_or_edge_verdict',)},
              'target_checks': [{'target': 'subject edge before approach catch-up',
                                 'requested': requested, 'measured': observed,
                                 'method': 'saved subject body edge and longitudinal gap',
                                 'tolerance': 0, 'matched': requested == observed,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full diagnostic 480-frame saved window',
              'physical_failure_flags': ['Original Native behavior and statutory sources unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if measurement['source_kind'] == 'synthetic_cpu' else 'original_native',
              'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
