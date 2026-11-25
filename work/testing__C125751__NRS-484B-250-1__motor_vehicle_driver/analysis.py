"""Saved-only source-bound finalizer for the C125751 operative-signal branch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_signal_audit import audit
from signal_crossing import validate_source_packet
from source_bindings import validate_review_refs


SOURCES = ('signal-packet.json', 'signal-history.json', 'reviewed-packet.json', 'review.json',
           'map.xodr', 'trace.jsonl', 'video_frames.jsonl',
           'acquisition-provenance.json')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _original(attempt, inventory, name):
    path = attempt / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    entry = inventory.get(name, {})
    if entry.get('kind') != 'original_native' or entry.get('sha256') != _sha(path):
        raise ValueError('Missing or stale original Native source: ' + name)
    return path


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Missing required source: ' + path.name)
    return rows


def build_report(attempt):
    attempt = Path(attempt)
    if not (attempt / 'acquisition.json').is_file():
        raise ValueError('Missing required source: acquisition.json')
    inventory = json.loads((attempt / 'acquisition.json').read_text())
    sources = {name: _original(attempt, inventory, name) for name in SOURCES}
    provenance = json.loads(sources['acquisition-provenance.json'].read_text())
    if (provenance.get('provenance_kind') not in ('native', 'synthetic_fixture') or
            provenance.get('review_sha256') != _sha(sources['review.json'])):
        raise ValueError('acquisition provenance differs from reviewed source')
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    packet = json.loads(sources['signal-packet.json'].read_text())
    reviewed_packet = json.loads(sources['reviewed-packet.json'].read_text())
    validate_source_packet(reviewed_packet, sources['map.xodr'].read_bytes(),
                           sources['review.json'].read_bytes())
    for ref in validate_review_refs(sources['review.json'].read_bytes(), attempt):
        _original(attempt, inventory, ref['path'])
    if (packet.get('map_sha256') != reviewed_packet['map_sha256'] or
            packet.get('review_sha256') != reviewed_packet['review_sha256'] or
            packet.get('crossing_id') != reviewed_packet['crossing_id']):
        raise ValueError('sealed Native history differs from reviewed source packet')
    if packet.get('map_sha256') != _sha(sources['map.xodr']):
        raise ValueError('Native map differs from retained reviewed source')
    report = audit(packet, sources['signal-history.json'].read_bytes(),
                   case_id, _sha(sources['review.json']))
    history = json.loads(sources['signal-history.json'].read_text())
    trace = _rows(sources['trace.jsonl'])
    mapping = _rows(sources['video_frames.jsonl'])
    frames = history['frames']
    if len(trace) != len(mapping) or len(trace) != len(frames):
        raise ValueError('Native trace, video and signal frame counts differ')
    for i, (row, mapped, signal) in enumerate(zip(trace, mapping, frames)):
        if (mapped.get('video_frame') != i or
                mapped.get('carla_frame') != row.get('frame') or
                abs(mapped.get('time_s', -1) - row.get('time_s', -2)) > 1e-6 or
                abs(signal['time_s'] - row['time_s']) > 1e-6):
            raise ValueError('Original video, trace and signal time join differs')
    hashes = {name: inventory[name]['sha256'] for name in SOURCES}
    reviewed_site = json.loads(sources['review.json'].read_text())
    values = {
        'entry_order': {'ego_entry_frame': report['ego_entry_frame'],
                        'other_entry_frame': report['other_entry_frame'],
                        'other_entered_first': report['other_entered_first']},
        'official_signal': {'initial': report['signal_initial_state'],
                            'transitions': report['signal_transition_frames'],
                            'operative_status': reviewed_site['device_review']['operative_status']},
        'route_context': {'crossing_id': reviewed_packet['crossing_id'],
                          'ego_highway': reviewed_packet['ego_highway'],
                          'other_highway': reviewed_packet['other_highway']},
        'subsection4_context': {'operative_status': reviewed_site['device_review']['operative_status'],
                                'separate_assignment': 'testing__C24811__NRS-484B-250-4__motor_vehicle_driver'},
    }
    measurements = {key: {'value': value, 'method': 'build_report', 'sources': hashes}
                    for key, value in values.items()}
    measurements['signal_crossing'] = {
                'value': report, 'method': 'sealed original body outlines and live signal readback',
                'sources': hashes}
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': measurements,
            'analysis_complete': True, 'legal_verdict_claimed': False,
            'limitations': ['Statutory applicability and right-of-way remain unresolved.',
                            'Source review and physical camera visibility require independent local audit.']}


def saved_result(attempt, report):
    from worker_exchange.native_output import validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    description = json.loads((attempt / 'construction.json').read_text())['recording_description']
    provenance_path = attempt / 'acquisition-provenance.json'
    provenance = json.loads(provenance_path.read_text())
    if provenance.get('provenance_kind') not in ('native', 'synthetic_fixture'):
        raise ValueError('acquisition provenance kind invalid')
    observed = report['measurements']['signal_crossing']['value']
    requested = config['case']['other_first']
    matched = observed['other_entered_first'] == requested
    requested_signal = config['case']['ego_light_request']
    signal_matched = (observed['signal_initial_state'] == requested_signal and
                      ('Green' in observed['signal_states_observed'] if requested_signal == 'Red'
                       else observed['signal_states_observed'] == ['Green']))
    sources = report['measurements']['signal_crossing']['sources']
    history = json.loads((attempt / 'signal-history.json').read_text())
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    reviewed = json.loads((attempt / 'reviewed-packet.json').read_text())
    rows = history['frames']
    channel_values = {
        'ego_body_history': [(row['time_s'], row['ego']['body_vertices_xy_m']) for row in rows],
        'other_body_history': [(row['time_s'], row['other']['body_vertices_xy_m']) for row in rows],
        'controller_history': [(row['time_s'], row.get('ego_next_tick_request')) for row in rows],
        'ego_light_readback': [(row['time_s'], row['ego_light_readback']) for row in rows],
        'ego_entry_frame': [(rows[observed['ego_entry_frame']]['time_s'], observed['ego_entry_frame'])],
        'other_entry_frame': [(rows[observed['other_entry_frame']]['time_s'], observed['other_entry_frame'])],
        'ego_clear_frame': [(rows[observed['ego_clear_frame']]['time_s'], observed['ego_clear_frame'])],
        'other_clear_frame': [(rows[observed['other_clear_frame']]['time_s'], observed['other_clear_frame'])],
        'official_device_inventory': [(rows[0]['time_s'], reviewed['official_device_inventory'])],
        'different_highway_identity': [(rows[0]['time_s'],
            {'ego': reviewed['ego_highway'], 'other': reviewed['other_highway']})],
    }
    for item in description['channels']:
        name = item['name']
        if name not in channel_values:
            raise ValueError('Unsupported declared channel: ' + name)
        if any(value is None for _, value in channel_values[name]):
            raise ValueError('Missing required source: ' + name)
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for time_s, value in channel_values[name]:
                stream.write(json.dumps({'time_s': time_s, 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': str(path.relative_to(attempt))})
    context_values = {
        'crossing_geometry': {'crossing_id': reviewed['crossing_id'],
                              'bounds_xy_m': reviewed['crossing_bounds_xy_m']},
        'highway_identity': {'ego': reviewed['ego_highway'],
                             'other': reviewed['other_highway']},
        'device_inventory': reviewed['official_device_inventory'],
        'driver_scope': json.loads((attempt / 'review.json').read_text())['driver_scope'],
    }
    context_path = channels / 'context.json'
    context_path.write_text(json.dumps(context_values, allow_nan=False) + '\n')
    for item in description.get('context_inputs', []):
        name = item['name']
        if name not in context_values:
            raise ValueError('Unsupported declared context: ' + name)
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': str(context_path.relative_to(attempt))})
    source_interval = [{'first_frame': history['frames'][0]['frame'],
                        'last_frame': history['frames'][-1]['frame'],
                        'first_time_s': history['frames'][0]['time_s'],
                        'last_time_s': history['frames'][-1]['time_s']}]
    check = lambda status, method: {'status': status, 'method': method,
        'intervals': source_interval, 'sources': sources, 'missing_evidence': [],
        'physical_causation_claimed': False}
    physical = {'setup': check('met' if signal_matched else 'not_met', 'reviewed map/device and live signal readback'),
                'target': check('met' if matched and signal_matched else 'not_met', 'original entry-order and signal comparison'),
                'maneuver': check('met', 'both bodies enter and clear one crossing'),
                'attempt': check('met', 'original body motion observed')}
    result = {'case_id': config['selected_case_id'],
              'measured_values': observed,
              'target_checks': [{'target': 'requested entry order',
                                 'requested': requested,
                                 'measured': observed['other_entered_first'],
                                 'method': 'original body-outline entry frames',
                                 'tolerance': 0, 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources},
                                {'target': 'operative signal readback',
                                 'requested': requested_signal,
                                 'measured': observed['signal_transition_frames'],
                                 'method': 'original live signal state on each frame',
                                 'tolerance': 0, 'matched': signal_matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': signal_matched, 'behavior_attempted': True,
              'maneuver_completed': True,
              'termination_reason': 'Saved original crossing history assessed',
              'physical_failure_flags': ([] if matched else ['entry_order_target_unmet']) +
                                        ([] if signal_matched else ['signal_readback_target_unmet']),
              'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': evidence,
              'realized_observables': {},
              'physical_checks': physical, 'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False,
              'provenance_kind': provenance['provenance_kind'],
              'diagnostic_fixture': provenance.get('diagnostic_fixture', True)}
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    with (args.attempt / 'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
