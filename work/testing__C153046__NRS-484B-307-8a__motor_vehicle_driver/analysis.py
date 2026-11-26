"""Recorded-only red-left measurement from sealed original Native sources."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from red_left_measurement import measure_exact, validate_site, _dot, _xy


def required(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build(attempt: Path) -> tuple[dict, dict]:
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    case = config['selected_case_id']
    if construction['case_id'] != case:
        raise ValueError('selected red-left construction differs')
    original = attempt / 'original-attempt'
    inventory = json.loads(required(attempt, 'original-attempt/inventory.json').read_text())
    if inventory.get('case_id') != case:
        raise ValueError('original inventory case changed')
    history = required(attempt, 'original-attempt/history.jsonl')
    frame_map = required(attempt, 'original-attempt/frame-map.json')
    packet = required(attempt, 'original-attempt/site-packet.json')
    if sha(history) != inventory.get('history_sha256') or \
            sha(frame_map) != inventory.get('frame_map_sha256') or \
            sha(packet) != inventory.get('site_sha256'):
        raise ValueError('sealed original red-left source changed')
    rows = read_rows(history)
    if len(rows) != config['frame_count'] and not (inventory.get('diagnostic_fixture') is True
                                                  and 2 <= len(rows) <= 20):
        raise ValueError('original red-left frame count differs')
    if any(row.get('case_id') != case or row.get('source_packet_sha256') != inventory['site_sha256']
           for row in rows):
        raise ValueError('original red-left case/source identity differs')
    for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        archive = original / (camera + '.zip')
        if archive.is_file():
            archive_bytes = archive.read_bytes()
        elif inventory.get('diagnostic_fixture') is True:
            archive_bytes = base64.b64decode(required(attempt,
                'original-attempt/' + camera + '.zip.b64').read_text().strip(), validate=True)
        else:
            raise ValueError('Missing original camera source: ' + camera)
        if hashlib.sha256(archive_bytes).hexdigest() != inventory.get('camera_media_sha256', {}).get(camera):
            raise ValueError('sealed original camera changed: ' + camera)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as frames:
            names = frames.namelist()
            expected = [f'{index:04d}-{row["native_frame"]["frame"]}.png'
                        for index, row in enumerate(rows)]
            if names != expected:
                raise ValueError('original camera/frame inventory differs: ' + camera)
            for row, name in zip(rows, names):
                raw = frames.read(name)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(raw).hexdigest() != \
                        row['camera_frames'][camera]['source_sha256']:
                    raise ValueError('original camera/frame source changed: ' + camera)
    maps = json.loads(frame_map.read_text())['frames']
    trace = read_rows(required(attempt, 'trace.jsonl'))
    video = read_rows(required(attempt, 'video_frames.jsonl'))
    if len(rows) != len(maps) or len(rows) != len(trace) or len(rows) != len(video):
        raise ValueError('original red-left frame/trace/video counts differ')
    for index, (row, mapped, motion, image) in enumerate(zip(rows, maps, trace, video)):
        native = row['native_frame']
        if mapped != {'video_frame': index, 'frame': native['frame'],
                      'time_s': native['time_s']} or \
                motion.get('frame') != native['frame'] or motion.get('time_s') != native['time_s'] or \
                image.get('video_frame') != index or image.get('carla_frame') != native['frame'] or \
                image.get('time_s') != native['time_s']:
            raise ValueError('original red-left timestamp/frame join differs')
    measurement = measure_exact(packet, history, case, attempt / 'case-plan.json')
    site = validate_site(packet, config['case']['draft_variables']['receiving_direction'])
    distance_by_frame = {}
    delay_by_frame = {}
    last_conflict_time = None
    first_release_delay = None
    for row in rows:
        native = row['native_frame']
        front = max(_dot(tuple(_xy(point, 'ego body')[i] - site['reference'][i]
                               for i in (0, 1)), site['direction'])
                    for point in native['ego']['body_vertices_xy'])
        distance_by_frame[native['frame']] = site['stop_progress_m'] - front
        if any(actor['conflict_zone_occupied'] for actor in native['directed_participants']):
            last_conflict_time = native['time_s']
        if (first_release_delay is None and last_conflict_time is not None and
                row.get('control_request', {}).get('action') == 'turn_left_request'):
            first_release_delay = native['time_s'] - last_conflict_time
        delay_by_frame[native['frame']] = first_release_delay or 0.0
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('refusing to overwrite prior red-left channels')
    channels.mkdir()
    observed = {
        'signal_red_alone': lambda row: row['native_frame']['signal_state'] == 'steady_red_alone',
        'stop_reference': lambda row: measurement['stop_reference_kind'],
        'pre_entry_stop': lambda row: row['native_frame']['ego']['speed_m_s'],
        'approach_lane': lambda row: row['native_frame']['ego']['lane_id'],
        'receiving_direction': lambda row: measurement['receiving_direction'],
        'directed_conflict': lambda row: any(
            actor['conflict_zone_occupied'] for actor in
            row['native_frame']['directed_participants']),
        'stop_reference_front_signed_distance': lambda row: distance_by_frame[row['native_frame']['frame']],
        'directed_conflict_release_delay': lambda row: delay_by_frame[row['native_frame']['frame']],
    }
    evidence = []
    description = construction['recording_description']
    for channel in description['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['native_frame']['time_s'],
                                         'value': observed[name](row)}, sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'reviewed_red_left_site_packet': {
        'sha256': inventory['site_sha256'], 'review_status':
        'pending independent original-source review'}}, sort_keys=True) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context.relative_to(attempt))})
    value = {'first_entry_frame': measurement['first_entry_frame'],
             'first_pre_entry_stop_frame': measurement['first_pre_entry_stop_frame'],
             'red_conflict_entry_frames': measurement['red_conflict_entry_frames'],
             'approach_lane_id': measurement['expected_approach_lane_id'],
             'receiving_direction': measurement['receiving_direction'],
             'stop_reference_kind': measurement['stop_reference_kind'],
             'legal_judgment': 'unresolved'}
    sources = {'original-attempt/history.jsonl': sha(history),
               'original-attempt/frame-map.json': sha(frame_map),
               'original-attempt/site-packet.json': sha(packet)}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'red_left_motion': {'value': value,
                                                 'method': 'build',
                                                 'sources': sources}},
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'limitations': ['Original signal and conflict evidence require review.',
                              'Diagnostic fixture is not a physical or legal finding.']}
    diagnostic = inventory.get('diagnostic_fixture') is True
    realized = {}
    plan_case = next(item for item in json.loads((attempt / 'case-plan.json').read_text())['cases']
                     if item['case_id'] == case)
    if plan_case.get('sweep_id'):
        proposal = json.loads((attempt / 'proposals/cases.json').read_text()) if \
            (attempt / 'proposals/cases.json').is_file() else None
        definitions = (next(item for item in proposal['cases'] if item['case_id'] == case)
                       ['sweep_measurements'] if proposal else config.get('sweep_measurements', []))
        for axis in definitions:
            name = axis['observable']
            values = [observed[name](row) for row in rows]
            statistic = axis['measurement']['statistic']
            realized[name] = {**axis['measurement'], 'unit': axis['unit'],
                              'value': min(values) if statistic == 'min' else values[-1],
                              'reference': 'channels/' + name + '.jsonl',
                              'sample_window_s': [rows[0]['native_frame']['time_s'],
                                                  rows[-1]['native_frame']['time_s']]}
    result = {'case_id': case, 'measured_values': value,
              'target_checks': [{'target': 'original stop, lane and directed conflict',
                                 'requested': config['case']['draft_variables'],
                                 'measured': value, 'method': 'measure_exact',
                                 'tolerance': 0, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner',
                                    'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': realized,
              'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False}
    return report, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, result = build(args.attempt)
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior red-left analysis report')
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
