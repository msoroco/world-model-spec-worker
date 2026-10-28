"""Assess measured pilot motion and emit a follow-up configuration decision."""
import argparse
import hashlib
import json
import pathlib
import statistics
import sys
from runner import route
for ancestor in pathlib.Path(__file__).resolve().parents:
    pipeline = ancestor / 'runtime/main-pipeline-v1/scenario_pipeline'
    if pipeline.is_dir():
        sys.path.insert(0, str(pipeline))
        break
from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def assess(attempt):
    attempt = pathlib.Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    samples = [json.loads(line) for line in (attempt / 'physical_samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (attempt / 'capture/evidence.jsonl').read_text().splitlines()]
    if not samples or len(samples) != len(mapping) or len(samples) != len(trace) or len(samples) != len(evidence):
        raise ValueError('Original sample/video/trace/evidence counts differ')
    if any(s['frame'] != m['native_frame'] or m.get('carla_frame') != t['frame'] or s['frame'] != t['frame'] or
           s['frame'] != e['original_frame'] or m['video_frame'] != i or
           abs(s['time_s'] - m['time_s']) > 1e-6
           for i, (s, m, t, e) in enumerate(zip(samples, mapping, trace, evidence))):
        raise ValueError('Original source frame or timestamp join differs')
    target = cfg['case']['variable_assignments']['commanded_approach_lateral']['value']
    approach = [s for s in samples if s['position_m'][0] < -11]
    offsets = [s['position_m'][1] for s in approach]
    approach_error = None if not offsets else statistics.mean(abs(x + target) for x in offsets)
    approach_target_met = approach_error is not None and approach_error <= 0.35
    native_edges = json.loads((attempt / 'native-topology.json').read_text())['edges']
    connector_observed = any(edge['from'][0] == 13 or edge['to'][0] == 13 for edge in native_edges)
    # The full vehicle footprint, not a lane-center lookup, determines whether
    # the approach stayed in its intended half of the constructed highway.
    footprints = [s['body_vertices_m'] for s in approach]
    footprint_inside = bool(footprints) and all(all(-7 <= v[1] <= 0 for v in body) for body in footprints)
    last = samples[-1] if samples else None
    completed = bool(last and last['route_index'] >= len(route(target)) - 1)
    channel_counts = {}
    for channel in cfg['case']['recording_description']['channels']:
        name = channel['name']
        rows = [json.loads(line) for line in (attempt / 'channels' / (name + '.jsonl')).read_text().splitlines()]
        if len(rows) != len(samples) or any(r['value'] is None or abs(r['time_s'] - s['time_s']) > 1e-6
                                            for r, s in zip(rows, samples)):
            raise ValueError('Mandatory channel count/time/value differs: ' + name)
        channel_counts[name] = len(rows)
    video_counts = {}
    mapping_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    videos = ['view%d.webm' % i for i in range(4)]
    if not all((attempt / video).is_file() for video in videos):
        if not (attempt / 'fixture-provenance.json').is_file() or not (attempt / 'raw.mkv').is_file():
            raise ValueError('Missing live camera recordings')
        videos = ['raw.mkv']
    for i, video in enumerate(videos):
        receipt = audit(attempt / video, len(samples), mapping_sha256=mapping_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if video.startswith('view'):
            expected_dimensions = [1920, 1080] if i == 0 else [1280, 720]
            if receipt['dimensions'] != expected_dimensions:
                raise ValueError('Decoded camera dimensions differ')
        video_counts[video] = receipt['frames']
    aligned = bool(samples and len(samples) == len(mapping) and
                   all(v == len(samples) for v in channel_counts.values()) and
                   all(v == len(samples) for v in video_counts.values()) and
                   all(a['frame'] == b['native_frame'] for a, b in zip(samples, mapping)))
    report = {'format': 'pilot-capability-report-v1', 'case_id': cfg['selected_case_id'],
              'sample_count': len(samples), 'approach_samples': len(approach),
              'mean_approach_abs_error_m': approach_error, 'full_footprint_in_right_half': footprint_inside,
              'approach_target_met_within_0_35_m': approach_target_met,
              'native_turn_connector_observed': connector_observed,
              'route_end_reached': completed, 'frame_and_channel_alignment': aligned,
              'channel_counts': channel_counts, 'decoded_video_counts': video_counts,
              'camera_visibility_verified': False,
              'physical_acceptance': False,
              'decision': 'inspect_native_evidence' if completed and footprint_inside and aligned and approach_target_met and connector_observed else 'repair_same_frozen_case',
              'follow_up': {'case_id': cfg['selected_case_id'], 'configuration': 'config.json',
                            'preserve_targets': True, 'requires_new_attempt': not (completed and footprint_inside and aligned and approach_target_met and connector_observed)}}
    measured = -statistics.mean(offsets) if offsets else -samples[0]['position_m'][1]
    target_check = {'target': 'commanded_approach_lateral', 'requested': target,
                    'measured': measured, 'method': 'negative mean original approach Y; first original Y for diagnostic subset without approach',
                    'tolerance': 0.35, 'matched': abs(measured-target) <= 0.35,
                    'physical_cause_confirmed': False, 'cause_evidence': 'physical_samples.jsonl'}
    recording_evidence = [{'name': channel['name'], 'unit': channel['unit'],
                           'reference': 'channels/' + channel['name'] + '.jsonl'}
                          for channel in cfg['case']['recording_description']['channels']]
    recording_evidence.append({'name': 'authored_context', 'unit': 'object', 'reference': 'context.json'})
    native_result = {'case_id': cfg['selected_case_id'], 'measured_values': {'approach_lateral_m': measured},
                     'target_checks': [target_check], 'setup_confirmed': False,
                     'behavior_attempted': bool(any(s.get('route_index', 0) > 0 for s in samples)),
                     'maneuver_completed': completed and not (attempt / 'fixture-provenance.json').exists(),
                     'termination_reason': 'route end observed' if completed else 'incomplete original trajectory',
                     'physical_failure_flags': {'visibility_unverified': True, 'physical_cause_unverified': True},
                     'trace_reference': 'trace.jsonl', 'video_references': videos,
                     'video_frame_map_reference': 'video_frames.jsonl',
                     'recording_description': cfg['case']['recording_description'],
                     'recording_evidence': recording_evidence, 'realized_observables': {}}
    return report, native_result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report, native_result = assess(args.attempt)
    write_result(args.attempt, native_result)
    pathlib.Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
