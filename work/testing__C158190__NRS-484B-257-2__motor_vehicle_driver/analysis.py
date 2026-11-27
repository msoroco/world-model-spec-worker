"""Recorded-only original stop-intersection finalizer.

Requested station and policy never substitute for original actor motion. Legal
hazard, caution and yielding classifications remain unresolved for review.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from nonthrough_stop import CASES, measure_frozen_windows
from stop_site import validate_site


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _scene(site: dict) -> dict:
    scene = {
        'cell_id': 'C158190', 'actor': 'motor_vehicle_driver',
        'ego_stop_sign': site['ego_stop_sign_present'],
        'non_through_highway': site['non_through_highway'],
        'officer_controls': site['officer_controls'],
        'signal_controls': site['signal_controls'],
        'other_vehicle_obligated_to_stop_or_yield':
            site['other_obligated_to_stop_or_yield'],
        'ego_route_xy': [point[:2] for point in
                         site['spawn_plan']['ego']['route_points_xyz_m']],
        'through_spawn_xy': site['spawn_plan']['other']['location_xyz_m'][:2],
        'stop_reference_station_m': site['stop_reference_station_m'],
        'intersection_entry_station_m': site['intersection_entry_station_m'],
    }
    for name in ('jurisdiction', 'intersection_geometry', 'all_entrance_controls',
                 'ego_stop_sign', 'non_through_classification', 'stop_reference',
                 'sightlines', 'through_vehicle_exemption', 'officer_control',
                 'signal_control', 'ego_vehicle'):
        scene[name + '_source_sha256'] = site['sources'][name]['sha256']
    return scene


def build(attempt: Path):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id:
        raise ValueError('selected original construction changed')
    suffix = case_id.rsplit('__', 1)[-1]
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None:
        raise ValueError('unsupported exact yield case')
    original = attempt / 'original-attempt'
    inventory = json.loads(required(attempt, 'original-attempt/inventory.json').read_text())
    history = required(attempt, 'original-attempt/history.jsonl')
    frame_map = required(attempt, 'original-attempt/frame-map.json')
    site_path = required(attempt, 'original-attempt/site-packet.json')
    diagnostic = inventory.get('diagnostic_fixture') is True
    if inventory.get('case_id') != case_id:
        raise ValueError('original yield inventory identity/provenance missing')
    for name, path in (('history_sha256', history), ('frame_map_sha256', frame_map),
                       ('site_sha256', site_path)):
        if inventory.get(name) != sha(path):
            raise ValueError('sealed original source changed: ' + name)
    site = validate_site(site_path, case_id)
    rows = _rows(history)
    maps = json.loads(frame_map.read_text()).get('frames')
    traces = _rows(required(attempt, 'trace.jsonl'))
    videos = _rows(required(attempt, 'video_frames.jsonl'))
    expected_count = len(rows) if diagnostic and 8 <= len(rows) <= 20 else 900
    if len(rows) != expected_count or not isinstance(maps, list) or \
            len(maps) != expected_count or len(traces) != expected_count or \
            len(videos) != expected_count:
        raise ValueError('original frame/trace/video sample count differs')
    for name in VIEWS:
        path = original / (name + '.zip')
        if path.is_file():
            media = path.read_bytes()
        elif diagnostic:
            media = base64.b64decode(required(attempt,
                'original-attempt/' + name + '.zip.b64').read_text().strip(), validate=True)
        else:
            raise ValueError('Missing original camera source: ' + name)
        if inventory.get('camera_media_sha256', {}).get(name) != hashlib.sha256(media).hexdigest():
            raise ValueError('sealed original camera changed: ' + name)
        with zipfile.ZipFile(io.BytesIO(media)) as archive:
            expected = [f'{i:04d}-{row["original_frame"]}.png'
                        for i, row in enumerate(rows)]
            if archive.namelist() != expected:
                raise ValueError('camera/frame source inventory differs: ' + name)
            for row, member in zip(rows, expected):
                raw = archive.read(member)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or \
                        hashlib.sha256(raw).hexdigest() != \
                        row['camera_frames'][name]['source_sha256']:
                    raise ValueError('original camera PNG changed: ' + name)
    observed = []
    for i, (row, mapped, trace, image) in enumerate(zip(rows, maps, traces, videos)):
        frame = row.get('original_frame')
        time_s = row.get('time_s')
        if row.get('case_id') != case_id or row.get('source_packet_sha256') != sha(site_path) or \
                mapped != {'video_frame': i, 'frame': frame, 'time_s': time_s} or \
                trace.get('frame') != frame or trace.get('time_s') != time_s or \
                image.get('video_frame') != i or image.get('carla_frame') != frame or \
                image.get('time_s') != time_s:
            raise ValueError('original yield frame/trace/video join differs')
        state = row.get('native_state')
        if not isinstance(state, dict):
            raise ValueError('original Native state missing')
        physical = {key: state[key] for key in (
            'ego_id', 'other_id', 'other_obligated_to_stop_or_yield',
            'officer_controls', 'signal_controls', 'ego_speed_mps',
            'ego_leading_station_m', 'other_center_station_m',
            'other_min_vertex_station_m', 'other_phase', 'ego_across_or_within',
            'ego_full_body_overlap', 'ego_full_body_cleared',
            'traffic_reference_event') if key in state}
        hashes = state.get('source_hashes', {})
        for name in ('source', 'ego_motion', 'other_motion', 'body_geometry',
                     'controls', 'sightlines', 'entrance_controls'):
            physical[name + '_sha256'] = hashes.get(name)
        physical.update(original_frame=frame, time_s=time_s,
                        intersection_geometry_source_sha256=
                            site['sources']['intersection_geometry']['sha256'],
                        all_entrance_controls_source_sha256=
                            site['sources']['all_entrance_controls']['sha256'])
        observed.append(physical)
    if diagnostic:
        if not any(row['ego_leading_station_m'] >= site['intersection_entry_station_m']
                   for row in observed) or not any(row['ego_across_or_within'] for row in observed):
            raise ValueError('diagnostic physical-entry shape absent')
        if observed[0]['other_phase'] != case.through_phase:
            raise ValueError('diagnostic requested other phase absent')
        measurement = {'case_id': suffix, 'frame_count': len(rows),
                       'first_original_entry_frame': next(row['original_frame'] for row in observed
                           if row['ego_leading_station_m'] >= site['intersection_entry_station_m']),
                       'frozen_observables': {}, 'legal_judgment': None,
                       'diagnostic_fixture': True}
    else:
        measurement = measure_frozen_windows(observed, _scene(site), case)
    sources = {'original-attempt/history.jsonl': sha(history),
               'original-attempt/frame-map.json': sha(frame_map),
               'original-attempt/site-packet.json': sha(site_path)}
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('refusing to overwrite prior original channels')
    channels.mkdir()
    values = {
        'non_through_classification': lambda row: site['non_through_highway'],
        'entrance_controls': lambda row: site['entrances'],
        'stop_sign': lambda row: site['ego_stop_sign_present'],
        'stop_reference': lambda row: site['stop_reference_station_m'],
        'ego_speed': lambda row: row['ego_speed_mps'],
        'ego_body_position': lambda row: row['ego_leading_station_m'],
        'other_body_position': lambda row: [row['other_center_station_m'],
                                            row['other_min_vertex_station_m']],
        'other_obligation': lambda row: row['other_obligated_to_stop_or_yield'],
        'other_phase': lambda row: row['other_phase'],
        'sightlines': lambda row: row['sightlines_sha256'],
        'officer_signal_control': lambda row: [row['officer_controls'],
                                                row['signal_controls']],
        'across_or_within': lambda row: row['ego_across_or_within'],
    }
    evidence = []
    description = construction['recording_description']
    for channel in description['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                            'value': values[name](row)}, sort_keys=True) + '\n'
                                for row in observed))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'reviewed_nonthrough_stop_site_packet': {
        'sha256': sha(site_path), 'review_status':
            'synthetic fixture' if diagnostic else 'pending independent original-source review'}},
        sort_keys=True) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context.relative_to(attempt))})
    value = {'motion': measurement, 'legal_judgment': 'unresolved'}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'measurements': {'nonthrough_stop_motion': {
                  'value': value, 'method': 'build', 'sources': sources}},
              'limitations': ['Original source review and law-specific hazard/caution '
                              'judgment remain pending.']}
    result = {'case_id': case_id, 'measured_values': value,
              'target_checks': [{'target': 'original non-through stop response',
                                 'requested': config['case']['draft_variables'],
                                 'measured': measurement, 'method': 'measure_frozen_windows',
                                 'tolerance': None, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'original physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': evidence, 'realized_observables':
                  measurement['frozen_observables'],
              'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False}
    return report, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior yield analysis report')
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
