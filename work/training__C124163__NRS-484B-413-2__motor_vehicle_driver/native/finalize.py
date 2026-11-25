"""Analyze retained signal-distance sources without asserting legal compliance."""
import argparse
import hashlib
import json
import math
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
THRESHOLDS_M = {'other_area': 91.44, 'business_or_residential': 30.48}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(root, name):
    path = root/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_signal_distance(measured):
    return {'continuous_native_light_state_distance_m': measured['distance_m'],
            'source_turn_request_frame': measured['turn_request_frame'],
            'visible_signal_distance_confirmed': False,
            'legal_verdict': None}


def source_weather_context(context):
    return {'district_requested': context['district_class_requested'],
            'weather_requested': context['weather_requested'],
            'district_originally_verified': context['district_class_originally_verified'],
            'weather_waiver_applied': False}


def reviewed_other_area_scope(context):
    return {'other_area_threshold_m': THRESHOLDS_M['other_area'],
            'district_requested': context['district_class_requested'],
            'original_class_verified': context['district_class_originally_verified']}


def reviewed_other_area_repeat(context):
    return {'same_source_scope': reviewed_other_area_scope(context),
            'independent_original_review_pending': True}


def analyze(root):
    config = json.loads(require(root, 'config.json').read_text())
    signal = rows(require(root, 'signal-source.jsonl'))
    mapping = rows(require(root, 'video_frames.jsonl'))
    trace = rows(require(root, 'trace.jsonl'))
    evidence = rows(require(root, 'capture/evidence.jsonl'))
    context = json.loads(require(root, 'context-review.json').read_text())
    for view in VIEWS:
        require(root, view+'.mkv')
    if not all(len(x) == 600 for x in (signal, mapping, trace, evidence)):
        raise ValueError('Full 600-frame saved source required')
    prev = None
    turn = []
    for i, (s, m, t, e) in enumerate(zip(signal, mapping, trace, evidence)):
        frame = m.get('native_frame')
        odometer = s.get('odometer_native_m')
        if (s.get('video_frame') != i or s.get('native_frame') != frame
                or t.get('frame') != frame or e.get('original_frame') != frame
                or type(odometer) not in (int, float) or not math.isfinite(odometer)
                or prev is not None and odometer < prev
                or type(s.get('left_blinker_state')) is not bool
                or type(s.get('course_change_requested')) is not bool):
            raise ValueError('Original signal, odometer and frame join failed')
        if s['course_change_requested'] and (i == 0 or not signal[i-1]['course_change_requested']):
            turn.append(i)
        prev = odometer
    if len(turn) != 1:
        raise ValueError('Exactly one course-change request onset required')
    onset = turn[0]
    start = onset
    while start > 0 and signal[start-1]['left_blinker_state']:
        start -= 1
    distance = signal[onset]['odometer_native_m'] - signal[start]['odometer_native_m']
    if distance < 0:
        raise ValueError('Negative signal distance')
    return {'distance_m': round(distance, 3), 'turn_request_frame': onset,
            'start_frame': start, 'context': context, 'signal': signal,
            'mapping': mapping}


def finalize(attempt, output):
    root = Path(attempt)
    config = json.loads(require(root, 'config.json').read_text())
    measured = analyze(root)
    context = measured['context']
    diagnostic = context.get('review_kind') == 'synthetic_diagnostic'
    inputs = ('signal-source.jsonl', 'video_frames.jsonl', 'context-review.json')
    methods = (measure_signal_distance, source_weather_context,
               reviewed_other_area_scope, reviewed_other_area_repeat)
    values = [methods[0](measured)] + [method(context) for method in methods[1:]]
    measurements = {}
    for index, (method, value) in enumerate(zip(methods, values)):
        name = ('continuous_signal_distance', 'weather_no_waiver',
                'other_area_review_scope', 'other_area_review_repeat')[index]
        measurements[name] = {'method': method.__name__, 'value': value,
                              'sources': {item: sha(root/item) for item in inputs}}
    channels = root/'channels'
    channels.mkdir(exist_ok=True)
    recording = []
    for item in config['recording_description']['channels']:
        name = item['name']
        path = channels/(name.replace('/', '_')+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s': frame['time_s'],
            'value': {'native_frame': frame['native_frame'],
                      'odometer_native_m': source['odometer_native_m'],
                      'left_blinker_state': source['left_blinker_state'],
                      'source_kind': source['source_kind']}}, separators=(',', ':'))+'\n'
            for frame, source in zip(measured['mapping'], measured['signal'])))
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/'+path.name})
    for item in config['recording_description']['context_inputs']:
        name = item['name']
        path = channels/(name+'.json')
        path.write_text(json.dumps({name: context}, separators=(',', ':'))+'\n')
        recording.append({'name': name, 'unit': item['unit'],
                          'reference': 'channels/'+path.name})
    result = {'case_id': config['case_id'],
        'measured_values': {'native_light_state_continuity_m': measured['distance_m'],
                            'legal_result': None},
        'target_checks': [{'target': 'requested_signal_distance_m',
                           'requested': config['requested_signal_distance_m'],
                           'measured': measured['distance_m'],
                           'method': 'source-joined post-tick Native odometer and light-state readback',
                           'tolerance': 0.4,
                           'matched': abs(config['requested_signal_distance_m']-measured['distance_m']) <= 0.4,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(inputs)}],
        'setup_confirmed': False, 'behavior_attempted': not diagnostic,
        'maneuver_completed': False,
        'termination_reason': 'synthetic diagnostic window' if diagnostic else 'original source window; review pending',
        'physical_failure_flags': ['visible_signal_district_turn_onset_review_pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name+'.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording,
        'realized_observables': {'native_light_state_continuity_m': {
            'value': measured['distance_m'], 'unit': 'm',
            'method': 'saved post-tick Native light-state and odometer join',
            'time_window': '600 frames', 'statistic': 'contiguous-before-request',
            'reference': 'signal-source.jsonl'}},
        'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root/'result.json').exists():
        raise ValueError('Saved processing cannot overwrite a prior result')
    (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    report = {'format': 'signal-distance-saved-analysis-v1',
              'case_id': config['case_id'], 'measurements': measurements,
              'original_native_source': not diagnostic,
              'visible_signal_pixels_reviewed': False, 'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': report['case_id'], 'legal_verdict': None}))
