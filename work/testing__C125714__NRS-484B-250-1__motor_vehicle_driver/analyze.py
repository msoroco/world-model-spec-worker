"""Measure original native capability observations without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def report_metrics(mode, attempt, trace, channels, config):
    physical = rows(attempt / 'physical_samples.jsonl') if (attempt / 'physical_samples.jsonl').is_file() else []
    values = {'source_frames': len(trace), 'diagnostic_subset': bool((attempt / 'fixture-provenance.json').exists())}
    if mode == 'crossing_priority':
        entry = lambda a: next((r['time_s'] for r in physical if r.get(a) and
            abs(r[a]['position_m'][0]) < 7 and abs(r[a]['position_m'][1] + 8) < 7), None)
        values.update(ego_entry_s=entry('ego'), other_entry_s=entry('other'),
                      earlier_other_entry_observed=entry('other') is not None and
                      (entry('ego') is None or entry('other') < entry('ego')))
    elif mode == 'divider_turn':
        opening = config['divider']['opening_x_m']
        crossing = [r for r in physical if r['ego']['position_m'][1] > 0]
        values.update(divider_crossing_samples=len(crossing),
                      crossing_within_opening=bool(crossing) and all(
                          opening[0] <= r['ego']['position_m'][0] <= opening[1] for r in crossing))
    elif mode == 'oneway':
        headings = [r['heading_deg'] for r in trace]
        values.update(observed_heading_span_deg=[min(headings), max(headings)],
                      positive_x_motion_observed=bool(physical) and
                      physical[-1]['ego']['position_m'][0] > physical[0]['ego']['position_m'][0])
    elif mode == 'speed':
        speeds = [r['speed_mps'] for r in trace]
        values.update(mean_original_speed_mps=sum(speeds) / len(speeds),
                      original_speed_range_mps=[min(speeds), max(speeds)],
                      native_visibility_calibration_present=(attempt / 'environment_calibration.json').is_file() and
                      not values['diagnostic_subset'])
    elif mode == 'signal':
        lamp = [r['value'] for r in channels['sig.turn_indicator']]
        illuminated = [r for r in lamp if isinstance(r, dict) and r.get('api_light_bits', 0)]
        path = [r['value'] for r in channels['kin.path_length']]
        values.update(native_indicator_samples=len(illuminated),
                      original_travel_m=max(path) - min(path) if path and all(isinstance(x,(int,float)) for x in path) else None,
                      rendered_lamp_phases_verified=False)
    return values, physical


def assess(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case']
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    if not trace or len(trace) != len(evidence) or len(trace) != len(frame_map):
        raise ValueError('Original trace/evidence/frame inventory differs')
    for i, (point, event, frame) in enumerate(zip(trace, evidence, frame_map)):
        if point['frame'] != event['original_frame'] or point['frame'] != frame.get('carla_frame') or \
                frame.get('native_frame') != point['frame'] or frame.get('video_frame') != i or \
                abs(point['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Original frame identity/time join differs')
    channels = {}
    for spec in case['recording_description']['channels']:
        name = spec['name']
        path = attempt / 'channels' / (name + '.jsonl')
        if not path.is_file():
            raise ValueError('Missing original acquisition channel: ' + name)
        stream = rows(path)
        if len(stream) != len(trace) or any(s.get('value') is None or
                abs(s['time_s'] - t['time_s']) > 1e-6 for s, t in zip(stream, trace)):
            raise ValueError('Original channel count/time/value differs: ' + name)
        channels[name] = stream
    fixture = (attempt / 'fixture-provenance.json').exists()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv' % i for i in range(4)]
    mapping_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    decoded = {}
    for i, video in enumerate(videos):
        file = attempt / video
        if not file.is_file():
            raise ValueError('Missing original camera: ' + video)
        receipt = audit(file, len(trace), mapping_sha256=mapping_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if not fixture and receipt['dimensions'] != ([1920,1080] if i == 0 else [1280,720]):
            raise ValueError('Original camera dimensions differ')
        decoded[video] = receipt['frames']
    measurements, physical = report_metrics(config['mode'], attempt, trace, channels, config)
    target = config['target_speed_mps']
    measured = trace[-1]['speed_mps']
    matched = abs(measured-target) <= 1.0
    endpoint = False
    if physical and not fixture:
        endpoint = physical[-1]['route_index'] >= config['route_points'] - 1
    native = {'case_id': case['case_id'], 'measured_values': measurements,
        'target_checks': [{'target': 'diagnostic_speed_sample_mps', 'requested': target,
                           'measured': measured, 'method': 'last original trace actor velocity norm',
                           'tolerance': 1.0, 'matched': matched,
                           'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'}],
        'setup_confirmed': False, 'behavior_attempted': bool(physical) and not fixture,
        'maneuver_completed': bool(endpoint),
        'termination_reason': 'diagnostic subset; physical maneuver unobserved' if fixture else
                              ('original route endpoint observed' if endpoint else 'original route incomplete'),
        'physical_failure_flags': {'physical_cause_unverified': True,
                                   'camera_visibility_unverified': True},
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': case['recording_description'],
        'recording_evidence': [{'name': spec['name'], 'unit': spec['unit'],
                                'reference': 'channels/' + spec['name'] + '.jsonl'}
                               for spec in case['recording_description']['channels']],
        'realized_observables': {}}
    report = {'format': 'partition02-capability-report-v1', 'case_id': case['case_id'],
              'mode': config['mode'], 'measurements': measurements,
              'source_video_frames': decoded, 'source_join': True,
              'physical_acceptance': False,
              'follow_up': {'case_id': case['case_id'], 'preserve_targets': True,
                            'requires_new_attempt': not endpoint},
              'unresolved': ['native motion and case-specific actuation',
                             'camera legibility and duration',
                             'public-way/device authority synthetic context',
                             'applicable unsupported adapter atoms recorded in HANDOFF.md']}
    return report, native


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report, native = assess(args.attempt)
    write_result(args.attempt, native)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
