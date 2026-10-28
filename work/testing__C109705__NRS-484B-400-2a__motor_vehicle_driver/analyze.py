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


def assess(attempt):
    attempt = pathlib.Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    samples = [json.loads(line) for line in (attempt / 'physical_samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (attempt / 'capture/evidence.jsonl').read_text().splitlines()]
    if not samples or len(samples) != len(mapping) or len(samples) != len(trace) or len(samples) != len(evidence):
        raise ValueError('Original sample/video/trace/evidence counts differ')
    if any(s['frame'] != m['native_frame'] or s['frame'] != t['frame'] or
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
    for i in range(4):
        receipt = audit(attempt / ('view%d.webm' % i), len(samples), mapping_sha256=mapping_sha,
                        receipt=attempt / ('view%d.source-decode.json' % i))
        expected_dimensions = [1920, 1080] if i == 0 else [1280, 720]
        if receipt['dimensions'] != expected_dimensions:
            raise ValueError('Decoded camera dimensions differ')
        video_counts['view%d' % i] = receipt['frames']
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
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    pathlib.Path(args.output).write_text(json.dumps(assess(args.attempt), indent=2) + '\n')
