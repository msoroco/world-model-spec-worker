"""Source-specific diagnostic finalizer; synthetic fixture never proves law or capture."""
import argparse
import hashlib
import json
from pathlib import Path

from device_scene import measure_attempt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_device_history(measured, site):
    return {'device_id': site['device_id'],
            'aspects': sorted({row['aspect'] for row in measured['frames']}),
            'governing_approach': site['ego_approach_id'],
            'placement_verdict': None}


def measure_bus_conduct(measured, site):
    return {'first_line_entry_frame': (measured['first_line_entry'] or {}).get('frame'),
            'first_signed_distance_m': measured['frames'][0]['bus_front_signed_distance_m'],
            'last_signed_distance_m': measured['frames'][-1]['bus_front_signed_distance_m'],
            'line_entry_observed': measured['first_line_entry'] is not None,
            'physical_completion_verdict': None}


def measure_police_direction(measured, site):
    sourced = [row for row in measured['frames'] if row.get('police_direction_source')]
    return {'observed_directions': sorted({row['police_direction'] for row in sourced}),
            'source_frames': [row['frame'] for row in sourced],
            'authority_verdict': None}


def measure_exception_context(measured, site):
    return {'context_sources': sorted({row['nrs_307_context_source'] for row in measured['frames']}),
            'statutory_applicability_verdict': None}


def analyze(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    note = json.loads(required(attempt, 'diagnostic-source-note.json').read_text())
    if note.get('source_kind') != 'synthetic_diagnostic_fixture' or note.get('accepted_original_source') is not False:
        raise ValueError('diagnostic provenance missing or falsely promoted')
    site = json.loads(required(attempt, 'site.json').read_text())
    rows_path = required(attempt, 'device-rows.json')
    measured = measure_attempt(site, attempt, {'path': 'device-rows.json', 'sha256': sha(rows_path)})
    rows = json.loads(rows_path.read_text())
    if len(rows) != 900 or any(row['frame'] != rows[0]['frame'] + index for index, row in enumerate(rows)):
        raise ValueError('900 joined synthetic diagnostic frames required')
    if any(row['aspect'] != config['case']['device_aspect'] for row in rows):
        raise ValueError('diagnostic governing device aspect changed')
    channels = config['case']['recording_description']['channels']
    values = {
        'device_aspect': lambda row, observed: row['aspect'],
        'bus_front_line_distance_m': lambda row, observed: observed['bus_front_signed_distance_m'],
        'police_direction': lambda row, observed: {'direction': row['police_direction'],
                                                    'source': row['police_direction_source']},
        'official_placement': lambda row, observed: row['placement_source'],
        'nrs_307_context': lambda row, observed: row['nrs_307_context_source'],
        'camera_frame_identity': lambda row, observed: row['frame'],
    }
    evidence = []
    for channel in channels:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown device recording channel')
        target = attempt / ('channel-' + name + '.jsonl')
        target.write_text(''.join(json.dumps({'time_s': index / 20,
                                               'value': values[name](row, observed)}) + '\n'
                                  for index, (row, observed) in enumerate(zip(rows, measured['frames']))))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': target.name})
    context_path = attempt / 'context-reviewed_device_site_packet.json'
    context_path.write_text(json.dumps({'reviewed_device_site_packet': {
        'site_sha256': sha(required(attempt, 'site.json')),
        'source_kind': 'synthetic_diagnostic_fixture',
        'accepted_original_source': False}}, indent=2) + '\n')
    evidence.append({'name': 'reviewed_device_site_packet', 'unit': 'source record',
                     'reference': context_path.name})
    sources = {name: sha(required(attempt, name)) for name in
               ('device-rows.json', 'site.json', 'diagnostic-source-note.json')}
    methods = (('official_device_measurement', measure_device_history),
               ('bus_conduct_measurement', measure_bus_conduct),
               ('police_direction_measurement', measure_police_direction),
               ('nrs_307_context_measurement', measure_exception_context))
    measurements = {name: {'method': method.__name__, 'value': method(measured, site),
                           'sources': sources} for name, method in methods}
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measurements,
              'target_checks': [{'target': 'bus front entry relative to reviewed stop line',
                                 'requested': config['case']['line_entry_request'],
                                 'measured': measured['first_line_entry'] is not None,
                                 'method': 'source-sealed bus-front positions and surveyed line',
                                 'tolerance': 0,
                                 'matched': (measured['first_line_entry'] is not None) == config['case']['line_entry_request'],
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_source_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': measurements, 'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; original device, authority and law remain source gated.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
