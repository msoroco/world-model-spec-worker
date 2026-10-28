"""Finalize measured partition-03 source evidence without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def assess(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case']
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    samples = rows(attempt / 'physical_samples.jsonl')
    if not trace or not (len(trace) == len(evidence) == len(mapping) == len(samples)):
        raise ValueError('Original trace/evidence/frame/sample inventory differs')
    for i, (point, event, frame, sample) in enumerate(zip(trace, evidence, mapping, samples)):
        if point['frame'] != event['original_frame'] or point['frame'] != frame.get('carla_frame') or \
                point['frame'] != sample['frame'] or frame.get('native_frame') != point['frame'] or \
                frame.get('video_frame') != i or abs(point['time_s'] - frame['time_s']) > 1e-6 or \
                abs(point['time_s'] - sample['time_s']) > 1e-6:
            raise ValueError('Original source identity/time join differs')
    channels = {}
    for spec in case['recording_description']['channels']:
        name = spec['name']
        path = attempt / 'channels' / (name + '.jsonl')
        if not path.is_file():
            raise ValueError('Original acquisition channel missing: ' + name)
        values = rows(path)
        if len(values) != len(trace) or any(v.get('value') is None or
                abs(v['time_s'] - t['time_s']) > 1e-6 for v, t in zip(values, trace)):
            raise ValueError('Original channel frame/time/value join differs: ' + name)
        channels[name] = [v['value'] for v in values]
    fixture = (attempt / 'fixture-provenance.json').exists()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv' % i for i in range(4)]
    mapping_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    decoded = {}
    for i, video in enumerate(videos):
        source = attempt / video
        if not source.is_file():
            raise ValueError('Original source camera missing: ' + video)
        receipt = audit(source, len(trace), mapping_sha256=mapping_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if not fixture:
            expected = [1920, 1080] if i == 0 else [1280, 720]
            if receipt['dimensions'] != expected:
                raise ValueError('Original camera dimensions differ')
        decoded[video] = receipt['frames']
    mode = config['mode']
    measurements = {'source_frames': len(trace), 'decoded_source_frames': decoded,
                    'source_join': True, 'scenario_mode': mode}
    if mode in ('signed_yield', 'signed_non_through'):
        requested = case['variable_assignments']['requested_wait_s']['value']
        stationary = [point for point in trace if point['position']['x'] < -6.0 and point['speed_mps'] < .1]
        measured = len(stationary) * .05
        target = 'pre_entry_stationary_duration_s'
        tolerance = .05
        visible_points = [point['position']['x'] for point, row in zip(trace, channels['visibility_rays'])
            if point['position']['x'] < -5 and any(hit.get('target_visible_by_ray')
            for hit in (row.get('same_frame') or []))]
        native_signs = channels['native_context'][0].get('native_sign_inventory')
        measurements.update({'pre_entry_stationary_duration_s': measured,
            'participant_frames': sum(bool(v.get('other')) for v in channels['participant_relation']),
            'authored_entrance_plan': channels['road_geometry'][0].get('signed_entrances'),
            'native_sign_inventory': native_signs,
            'first_sampled_visible_approach_x_m': visible_points[0] if visible_points else None,
            'immediate_hazard_standard': 'unresolved legal judgment'})
    elif mode == 'curve_u_turn':
        requested = case['variable_assignments']['sight_probe_m']['value']
        ranges = [v.get('sampled_visible_range_m') for v in channels['visibility_rays']]
        measured = min(v for v in ranges if isinstance(v, (float, int))) if any(
            isinstance(v, (float, int)) for v in ranges) else 0.0
        target = 'sampled_bidirectional_visible_range_m'
        tolerance = .1
        headings = [point['heading_deg'] for point in trace]
        measurements.update({'sampled_bidirectional_visible_range_m': measured,
            'heading_delta_deg': ((headings[-1] - headings[0] + 180) % 360) - 180,
            'visibility_method': 'native two-direction case-specific finite probe rays; finite grid only'})
    elif mode == 'truck_follow':
        requested = case['variable_assignments']['requested_gap_m']['value']
        gaps = [v.get('gap_m') for v in channels['surface_gap']]
        valid = [v for v in gaps if isinstance(v, (float, int))]
        measured = sum(valid) / len(valid) if valid else 0.0
        target = 'mean_original_body_surface_gap_m'
        tolerance = 2.0
        measurements.update({'mean_original_body_surface_gap_m': measured,
            'measured_gap_frames': len(valid),
            'measured_body_widths_m': channels['surface_gap'][0].get('measured_widths'),
            'qualifying_80_inch_width_from_body': all(isinstance(w, (float, int)) and w >= 2.032
                for w in channels['surface_gap'][0].get('measured_widths', {}).values()),
            'native_goods_transport_class_unverified': True,
            'conditions_permit_standard': 'unresolved legal judgment'})
    elif mode == 'reverse_crosswalk':
        requested = case['variable_assignments']['reverse_overlap_target']['value']
        overlap = any(v.get('body_overlap') and v.get('reverse_control')
                      for v in channels['crosswalk_overlap'])
        measured = int(overlap)
        target = 'simultaneous_reverse_crosswalk_overlap'
        tolerance = 0
        measurements.update({'simultaneous_reverse_crosswalk_overlap': bool(overlap),
            'crosswalk_marking_unverified': True})
    else:
        raise ValueError('Unknown mode')
    endpoints = config['route_end_m']
    last = trace[-1]['position']
    endpoint = abs(last['x'] - endpoints[0]) <= 2.0 and abs(last['y'] - endpoints[1]) <= 2.0
    maneuver_completed = bool(endpoint and not fixture)
    native = {'case_id': case['case_id'], 'measured_values': measurements,
        'target_checks': [{'target': target, 'requested': requested, 'measured': measured,
                           'method': 'same-frame original channel and trace history; diagnostic subset is software only',
                           'tolerance': tolerance, 'matched': abs(measured-requested) <= tolerance,
                           'physical_cause_confirmed': False,
                           'cause_evidence': 'physical_samples.jsonl and channels/'+(
                               'surface_gap' if mode == 'truck_follow' else
                               'visibility_rays' if mode == 'curve_u_turn' else
                               'crosswalk_overlap' if mode == 'reverse_crosswalk' else 'motion_event')+'.jsonl'}],
        'setup_confirmed': False, 'behavior_attempted': not fixture and len(trace) > 1,
        'maneuver_completed': maneuver_completed,
        'termination_reason': 'diagnostic subset; maneuver unverified' if fixture else
                              ('measured route endpoint' if endpoint else 'incomplete original route'),
        'physical_failure_flags': {'native_scene_unverified': True,
                                   'camera_visibility_unverified': True},
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': case['recording_description'],
        'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                'reference': 'channels/'+c['name']+'.jsonl'}
                               for c in case['recording_description']['channels']],
        'realized_observables': {}}
    report = {'format': 'partition03-capability-report-v1', 'case_id': case['case_id'],
              'measurements': measurements, 'target_check': native['target_checks'][0],
              'route_endpoint_observed': endpoint, 'physical_acceptance': False,
              'follow_up': {'same_case_id': case['case_id'], 'preserve_targets': True,
                            'requires_new_attempt': not maneuver_completed},
              'unresolved': ['native motion and authored geometry',
                             'public-way/device authority or truck qualification as applicable',
                             'camera pixel visibility and duration',
                             'legal judgment standards remain unselected']}
    return report, native


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report, native = assess(args.attempt)
    write_result(args.attempt, native)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
