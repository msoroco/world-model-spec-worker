"""Recorded-only finalization of device, civil and visibility sources."""
import argparse
import hashlib
import json
from pathlib import Path

from civil_time_measure import measure as civil_measure
from lamp_full_measure import measure_original as lamp_measure_original
from visibility_measure import CAMERAS, measure as visibility_measure


SOURCES = ('visibility-trace.jsonl', 'video_frames.jsonl', 'road.xodr',
           'visibility-context.json', 'visibility-pixel-review.json',
           'civil-clock.json', 'civil-time-review.json', 'sun-event-source.json',
           'location-source.json', 'vehicle-lamps.jsonl', 'lamp-context.json',
           'lamp-source-review.json', 'highway-review.json',
           'vehicle-class-review.json', 'device-content-review.json',
           'device-authority-review.json', 'device-placement-review.json',
           'device-timing-review.json') + tuple(name+'.mkv' for name in CAMERAS)

REVIEW_SOURCES = {
    'highway_source_sha256': 'highway-review.json',
    'vehicle_class_source_sha256': 'vehicle-class-review.json',
    'device_content_source_sha256': 'device-content-review.json',
    'device_authority_source_sha256': 'device-authority-review.json',
    'device_placement_source_sha256': 'device-placement-review.json',
    'device_timing_source_sha256': 'device-timing-review.json',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, name):
    path = root/name
    require(path.is_file(), 'Missing required source: '+name)
    return path.read_bytes()


def reviewed_measure(raw):
    """Join Native lamp, civil and visibility samples to independent reviews."""
    pixel = json.loads(raw['visibility-pixel-review.json'])
    context = json.loads(raw['visibility-context.json'])
    for role in ('person', 'vehicle'):
        name = pixel.get(role+'_video')
        require(name in [camera+'.mkv' for camera in CAMERAS],
                'Original '+role+' camera missing')
        if context.get('source_kind') == 'native_saved_sample':
            require(pixel.get(role+'_video_sha256') == sha(raw[name]),
                    'Original '+role+' video hash changed')
    civil_review = json.loads(raw['civil-time-review.json'])
    require(civil_review.get('sun_event_source_sha256') == sha(raw['sun-event-source.json']),
            'Dated sun-event source hash changed')
    require(civil_review.get('location_source_sha256') == sha(raw['location-source.json']),
            'Independent location source hash changed')
    visibility = visibility_measure(raw['visibility-trace.jsonl'], raw['road.xodr'],
                                    raw['visibility-pixel-review.json'],
                                    raw['visibility-context.json'],
                                    raw['video_frames.jsonl'])
    civil = civil_measure(raw['civil-clock.json'], raw['civil-time-review.json'])
    original_lamp = json.loads(raw['lamp-context.json'])
    lamp_review = json.loads(raw['lamp-source-review.json'])
    kind = context.get('source_kind')
    require(original_lamp.get('source_kind') == kind and
            lamp_review.get('case_id') and
            lamp_review.get('original_context_sha256') == sha(raw['lamp-context.json']) and
            lamp_review.get('review_kind') == ('original_source_review' if
                kind == 'native_saved_sample' else 'synthetic_diagnostic'),
            'independent device review does not bind original lamp context')
    sourced_lamp = dict(original_lamp)
    for field in ('state', 'public_highway', 'vehicle_class', 'directive',
                  'device_official', 'device_governs_road_id'):
        sourced_lamp[field] = lamp_review.get(field)
    for field, name in REVIEW_SOURCES.items():
        require(lamp_review.get(field) == sha(raw[name]),
                'independent device source hash differs: '+name)
        independent = json.loads(raw[name])
        require(independent.get('case_id') == lamp_review['case_id'] and
                independent.get('review_kind') == lamp_review['review_kind'],
                'independent device review provenance differs: '+name)
        sourced_lamp[field] = sha(raw[name])
    lamp = lamp_measure_original(raw['vehicle-lamps.jsonl'],
                                 raw['video_frames.jsonl'],
                                 json.dumps(sourced_lamp, sort_keys=True).encode(),
                                 raw['road.xodr'])
    lamp_rows = [json.loads(line) for line in raw['vehicle-lamps.jsonl'].splitlines() if line]
    visibility_rows = [json.loads(line) for line in raw['visibility-trace.jsonl'].splitlines() if line]
    require(len(lamp_rows) == len(visibility_rows) == 600 and all(
        a['native_frame'] == b['native_frame'] and
        a['video_frame'] == b['video_frame'] and
        a['camera_native_frames'] == b['camera_native_frames'] and
        abs(a['time_s']-b['time_s']) < 1e-8
        for a, b in zip(lamp_rows, visibility_rows)),
        'original device and visibility frame joins differ')
    return {'lamp_device': lamp, 'visibility': visibility, 'civil_time': civil,
            'legal_verdict_claimed': False}


def finalize(attempt, output):
    root = Path(attempt)
    output = Path(output)
    require(not output.exists() and not (root/'result.json').exists(),
            'fresh recorded-only finalization required')
    config = json.loads(read(root, 'config.json'))
    raw = {name: read(root, name) for name in SOURCES}
    require(json.loads(raw['lamp-source-review.json']).get('case_id') == config['case_id'],
            'independent device review selects another case')
    source_kind = json.loads(raw['visibility-context.json']).get('source_kind')
    require(source_kind in ('native_saved_sample', 'synthetic_diagnostic'),
            'explicit original or diagnostic provenance required')
    measured = reviewed_measure(raw)
    hashes = {name: sha(value) for name, value in raw.items()}
    analysis = {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
                'measurements': {'lamp_device_measurement': {
                    'method': 'reviewed_measure', 'value': measured, 'sources': hashes}},
                'legal_verdict_claimed': False}
    trace = [json.loads(line) for line in raw['visibility-trace.jsonl'].splitlines() if line]
    frames = [json.loads(line) for line in raw['video_frames.jsonl'].splitlines() if line]
    require(len(trace) == len(frames) == 600, 'original 600-frame join missing')
    trace_path = root/'trace.jsonl'
    rows = []
    for item in trace:
        xy = item['ego_xy_m']
        rows.append({'frame': item['native_frame'], 'time_s': item['time_s'],
                     'position': {'x': xy[0], 'y': xy[1], 'z': 0},
                     'position_m': [xy[0], xy[1], 0], 'heading_deg': 0,
                     'speed_mps': item.get('ego_speed_mps', 0),
                     'speed_mph': item.get('ego_speed_mps', 0)/.44704,
                     'velocity_mps': [item.get('ego_speed_mps', 0), 0, 0],
                     'control': {}})
    derived = ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows).encode()
    if trace_path.is_file():
        require(trace_path.read_bytes() == derived,
                'original trace differs from visibility source')
    else:
        trace_path.write_bytes(derived)
    channels = root/'channels'
    channels.mkdir(exist_ok=True)
    channel_data = {
        'native_lamp_setting': [
            {'time_s': item['time_s'],
             'value': {'native_light_state_bits': item.get('ego_light_state_bits')}}
            for item in trace],
        'device_and_highway_context': [
            {'time_s': item['time_s'],
             'value': {'road_id': 1, 'official_device_reviewed': False}}
            for item in trace],
        'person_visibility_1000ft': [
            {'time_s': item['time_s'],
             'value': {'forward_distance_m': item['person_forward_distance_m']}}
            for item in trace],
        'vehicle_visibility_1000ft': [
            {'time_s': item['time_s'],
             'value': {'forward_distance_m': item['vehicle_forward_distance_m']}}
            for item in trace],
        'civil_time_and_sun_events': [
            {'time_s': item['time_s'],
             'value': {'civil_time_iso': item.get('civil_time_iso')}}
            for item in trace],
    }
    for name, rows in channel_data.items():
        (channels/(name+'.jsonl')).write_text(''.join(
            json.dumps(row, allow_nan=False)+'\n' for row in rows))
    result = {'case_id': config['case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'device-directed Native lamp setting',
                                 'requested': config['lamp_setting_on'],
                                 'measured': {'governed_frames': len(
                                     measured['lamp_device']['governed_frames']),
                                     'both_settings_on_frames': len(
                                     measured['lamp_device']['both_settings_on_frames'])},
                                 'method': 'original light-state readback and independent device sources',
                                 'tolerance': None,
                                 'matched': bool(measured['lamp_device']['governed_frames'])
                                    and ((set(measured['lamp_device']['governed_frames']) ==
                                          set(measured['lamp_device']['both_settings_on_frames']))
                                         if config['lamp_setting_on'] else
                                         not measured['lamp_device']['both_settings_on_frames']),
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(hashes)},
                                {'target': 'source-bound civil and 1,000-foot geometry',
                                 'requested': config['boundary_request'],
                                 'measured': {'civil_trigger_frames': len(measured['civil_time']['trigger_frames']),
                                              'person_reference_frames': len(measured['visibility']['person_source_frames']),
                                              'vehicle_reference_frames': len(measured['visibility']['vehicle_source_frames'])},
                                 'method': 'original Native frame join with independent sources',
                                 'tolerance': None, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(hashes)}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'original physical and legal review pending',
              'physical_failure_flags': ['independent source review required'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name+'.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [
                  {'name': name, 'unit': 'boolean' if name == 'native_lamp_setting'
                   else 'structured', 'reference': 'channels/'+name+'.jsonl'}
                  for name in channel_data] + [
                      {'name': item['name'], 'unit': item['unit'],
                       'reference': 'visibility-context.json'}
                      for item in config['recording_description']['context_inputs']],
              'realized_observables': {}, 'provenance_kind': source_kind,
              'diagnostic_fixture': source_kind == 'synthetic_diagnostic',
              'accepted': False,
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    output.write_text(json.dumps(analysis, indent=2)+'\n')
    write_result(root, result)
    return analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
