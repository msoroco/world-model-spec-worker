"""Saved red-plus-arrow measurements from sealed original or explicit CPU diagnostics.

The diagnostic branch checks software shape only. A physical claim requires the
original site, telemetry, frame map and all 2,400 camera images checked by
saved_turn.audit_saved_attempt; neither branch emits a legal verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_turn import audit_case_measurement, point_in_polygon
from saved_turn import audit_saved_attempt

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('red-arrow-observations.json', 'source_site.json')
KEYS = ('signal_and_movement', 'pedestrian_precedence',
        'other_traffic_precedence', 'opposing_red_advisory', 'exception_actor_scope')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(attempt, acquisition, name):
    path = attempt / name
    if not path.is_file() or acquisition.get(name, {}).get('sha256') != sha(path):
        raise ValueError('Missing required source: ' + name)
    return path


def source_rows(attempt, config):
    provenance = attempt / 'fixture-provenance.json'
    if provenance.is_file():
        fixture = json.loads(provenance.read_text())
        if fixture.get('diagnostic_fixture') is not True or fixture.get('physical_acceptance_claimed') is not False:
            raise ValueError('diagnostic provenance is not explicit nonacceptance')
        acquisition = json.loads((attempt / 'acquisition.json').read_text())
        paths = {name: required(attempt, acquisition, name) for name in SOURCES}
        site = json.loads(paths['source_site.json'].read_text())
        if site.get('source_kind') != 'cpu_diagnostic_only':
            raise ValueError('diagnostic source site is not labeled')
        rows = json.loads(paths['red-arrow-observations.json'].read_text())
        if not isinstance(rows, list) or len(rows) < 3:
            raise ValueError('case-specific original-shaped observations missing')
        if [r.get('frame') for r in rows] != list(range(len(rows))):
            raise ValueError('diagnostic frame sequence differs')
        if site.get('case_id') != config['selected_case_id']:
            raise ValueError('diagnostic exact case differs')
        return rows, site, {name: sha(path) for name, path in paths.items()}, True
    manifest = attempt / 'manifest.json'
    if not manifest.is_file():
        raise ValueError('Missing required source: manifest.json')
    seal = audit_saved_attempt(attempt, {'path': 'manifest.json', 'sha256': sha(manifest)})
    source = json.loads(manifest.read_text())
    if source.get('case_suffix') != config['case_suffix']:
        raise ValueError('sealed original exact case differs')
    site = json.loads(required(attempt, {'site.json': source['site']}, 'site.json').read_text())
    rows = json.loads(required(attempt, {'telemetry.json': source['telemetry']}, 'telemetry.json').read_text())
    crosswalk_ref = site['original_sources']['crosswalk']
    permission_ref = site['original_sources']['pedestrian_permission']
    crosswalk = json.loads(required(attempt, {crosswalk_ref['path']: crosswalk_ref}, crosswalk_ref['path']).read_text())
    permission = json.loads(required(attempt, {permission_ref['path']: permission_ref}, permission_ref['path']).read_text())
    site['pedestrian_permission_source_id'] = permission['source_id']
    rows = [dict(row, pedestrian_inside_adjacent_crosswalk=
                 point_in_polygon(row['pedestrian_xy'], crosswalk['polygon_xy'])) for row in rows]
    return rows, site, {'manifest.json': sha(manifest),
                        'site.json': source['site']['sha256'],
                        'telemetry.json': source['telemetry']['sha256']}, False


def measure_case(rows, site, suffix):
    if not rows or site.get('actor') != 'motor_vehicle_driver':
        raise ValueError('source actor or measurements missing')
    if site.get('arrow_destination_lane_id') == site.get('straight_destination_lane_id'):
        raise ValueError('arrow and straight routes are not distinct')
    measured_rows = []
    for row in rows:
        if (row.get('ego_red') is not True or row.get('opposing_red') is not True or
                row.get('ego_arrow_direction') != site.get('arrow_direction') or
                row.get('ego_head_id') != site.get('ego_head_id') or
                row.get('opposing_head_id') != site.get('opposing_head_id')):
            raise ValueError('original red-plus-arrow or opposing red observation missing')
        if row.get('pedestrian_permission_source_id') != site.get('pedestrian_permission_source_id'):
            raise ValueError('pedestrian permission source differs')
        if row.get('other_traffic_actor_id') != site.get('other_traffic_actor_id'):
            raise ValueError('other traffic source identity differs')
        measured_rows.append({'frame': row['frame'],
            'pedestrian_inside_adjacent_crosswalk': row['pedestrian_inside_adjacent_crosswalk'],
            'pedestrian_lawful_context': row['pedestrian_lawful_context'],
            'other_traffic_lawfully_in_intersection': row['other_traffic_lawful_context'] and row['other_traffic_in_intersection'],
            'ego_in_intersection': row['ego_in_intersection'],
            'ego_route_lane_id': row['ego_route_lane_id'],
            'ego_speed_mps': row['ego_speed_mps']})
    entries = [r for r in measured_rows if r['ego_in_intersection']]
    if not entries:
        raise ValueError('actual intersection entry missing')
    measured = {'measurements': measured_rows, 'first_ego_entry': entries[0],
                'arrow_destination_lane_id': site['arrow_destination_lane_id']}
    distinction = audit_case_measurement(suffix, measured)
    entry = entries[0]
    return {'signal_and_movement': {'entry_frame': entry['frame'],
                                    'actual_destination_lane_id': entry['ego_route_lane_id'],
                                    'arrow_destination_lane_id': site['arrow_destination_lane_id']},
            'pedestrian_precedence': {'present_before_entry': any(r['pedestrian_inside_adjacent_crosswalk'] and r['pedestrian_lawful_context'] for r in measured_rows if r['frame'] <= entry['frame']),
                                      'occupied_at_entry': entry['pedestrian_inside_adjacent_crosswalk'] and entry['pedestrian_lawful_context']},
            'other_traffic_precedence': {'present_before_entry': any(r['other_traffic_lawfully_in_intersection'] for r in measured_rows if r['frame'] <= entry['frame']),
                                         'occupied_at_entry': entry['other_traffic_lawfully_in_intersection']},
            'opposing_red_advisory': {'observed_frames': len(rows), 'opposing_head_id': site['opposing_head_id']},
            'exception_actor_scope': {'actor': site['actor'], 'paragraph_b_applied': False},
            'distinction': distinction}


def build_report(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    rows, site, hashes, diagnostic = source_rows(attempt, config)
    values = measure_case(rows, site, config['case_suffix'])
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {key: {'value': values[key], 'method': 'measure_case',
                                   'sources': hashes} for key in KEYS},
            'distinction': values['distinction'], 'diagnostic_fixture': diagnostic,
            'analysis_complete': True, 'legal_verdict_claimed': False,
            'limitations': ['Lawful presence and right of way require original source review.',
                            'Synthetic diagnostic pixels do not establish physical completion.']}, rows, site


def saved_result(attempt, report, rows, site):
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    planned = construction['recording_description']
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines() if line]
    if len(rows) != len(mapping):
        raise ValueError('original source/frame map count differs')
    output = attempt / 'channels'
    output.mkdir(exist_ok=False)
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        path = output / (name + '.jsonl')
        with path.open('x') as stream:
            for index, (row, frame) in enumerate(zip(rows, mapping)):
                if frame.get('video_frame') != index:
                    raise ValueError('original video frame identity differs')
                value = frame if name == 'camera_frame_map' else row
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = output / 'context.json'
    context.write_text(json.dumps({'reviewed_original_site': site}, allow_nan=False) + '\n')
    evidence.append({'name': 'reviewed_original_site', 'unit': 'structured record',
                     'reference': str(context.relative_to(attempt))})
    result = {'case_id': config['selected_case_id'],
              'measured_values': {key: report['measurements'][key]['value'] for key in KEYS},
              'target_checks': [{'target': 'source-bound red-plus-arrow case distinction',
                                 'requested': config['case_suffix'],
                                 'measured': report['distinction']['case_suffix'],
                                 'method': 'measure_case', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': report['measurements']['signal_and_movement']['sources']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Saved original review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned, 'recording_evidence': evidence,
              'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt)
    report, rows, site = build_report(attempt)
    result = saved_result(attempt, report, rows, site)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    with (attempt / 'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
