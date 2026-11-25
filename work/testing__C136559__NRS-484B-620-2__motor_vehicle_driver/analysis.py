"""Recorded-only speed-zone finalizer with explicit synthetic source separation."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from saved_audit import audit as audit_saved
from speed_site import validate_packet
from speed_zone import measure_original

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, relative):
    path = Path(root) / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def build(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id:
        raise ValueError('selected original construction changed')
    original = attempt / 'original-attempt'
    capture_path = required(attempt, 'original-attempt/capture.json')
    seal_path = required(attempt, 'original-attempt/capture-source-seal.json')
    site_path = required(attempt, 'original-attempt/site-packet.json')
    _, site, case = validate_packet(site_path, case_id)
    capture = json.loads(capture_path.read_text())
    seal = json.loads(seal_path.read_text())
    if seal.get('case_id') != case_id or seal.get('capture_sha256') != sha(capture_path):
        raise ValueError('original speed capture seal mismatch')
    if capture.get('case_id') != case_id or capture.get('law_id') != 'NRS-484B-620-2' or \
            capture.get('cell_id') != 'C136559':
        raise ValueError('original speed capture identity mismatch')
    diagnostic = capture.get('diagnostic_fixture') is True
    if not diagnostic:
        audit_saved(capture_path, seal_path, case_id)
    rows = capture.get('original_rows')
    frame_map = json.loads(required(attempt, 'original-attempt/frame-map.json').read_text())
    traces = lines(required(attempt, 'trace.jsonl'))
    video_frames = lines(required(attempt, 'video_frames.jsonl'))
    count = len(rows) if diagnostic and isinstance(rows, list) and 8 <= len(rows) <= 20 else 900
    mappings = frame_map.get('frames')
    if not isinstance(rows, list) or len(rows) != count or not isinstance(mappings, list) or \
            len(mappings) != count or len(traces) != count or len(video_frames) != count:
        raise ValueError('original speed frame/trace/video sample count differs')
    for index, (row, mapping, trace, video) in enumerate(zip(rows, mappings, traces, video_frames)):
        expected_frame = rows[0]['original_frame'] + index
        if row.get('original_frame') != expected_frame or mapping.get('video_frame') != index or \
                mapping.get('original_frame') != expected_frame or trace.get('original_frame') != expected_frame or \
                video.get('original_frame') != expected_frame or video.get('video_frame') != index or \
                row.get('source_sha256') != sha(site_path):
            raise ValueError('original speed frame/trace/video join differs')
    for name in VIEWS:
        camera = original / (name + '.zip')
        if camera.is_file():
            media = camera.read_bytes()
        elif diagnostic:
            media = base64.b64decode(required(attempt,
                'original-attempt/' + name + '.zip.b64').read_text().strip(), validate=True)
        else:
            raise ValueError('Missing original camera source: ' + name)
        with zipfile.ZipFile(io.BytesIO(media)) as archive:
            if archive.namelist() != [f'{i:04d}.png' for i in range(count)]:
                raise ValueError('original speed camera/frame inventory differs: ' + name)
            for index in range(count):
                raw = archive.read(f'{index:04d}.png')
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or \
                        hashlib.sha256(raw).hexdigest() != \
                        mappings[index]['camera_frames'][name]['sha256']:
                    raise ValueError('original speed camera PNG changed: ' + name)
    measurement = measure_original(rows, case)
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('refusing to overwrite original speed channels')
    channels.mkdir()
    values = {'actual_speed_mps': lambda row: row['actual_speed_mps'],
              'inside_zone': lambda row: row['inside_zone'],
              'sign_installed': lambda row: row['sign_installed'],
              'authorized_speed_mph': lambda row: site['authorized_speed_mph'],
              'vehicle_class': lambda row: row['vehicle_class']}
    evidence = []
    description = construction['recording_description']
    for channel in description['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['original_time_s'],
                                            'value': values[name](row)}, sort_keys=True) + '\n'
                                for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context = channels / 'context.json'
    context.write_text(json.dumps({'reviewed_speed_site_packet': {
        'sha256': sha(site_path), 'review_status': 'synthetic fixture' if diagnostic
        else 'pending independent original review'}}, sort_keys=True) + '\n')
    evidence.append({'name': 'reviewed_speed_site_packet', 'unit': 'source record',
                     'reference': str(context.relative_to(attempt))})
    sources = {'original-attempt/capture.json': sha(capture_path),
               'original-attempt/capture-source-seal.json': sha(seal_path),
               'original-attempt/site-packet.json': sha(site_path)}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'analysis_complete': True, 'legal_verdict_claimed': False,
              'measurements': {'speed_zone_history': {
                  'value': measurement, 'method': 'build', 'sources': sources}},
              'limitations': ['Original sign appropriateness and legal outcome require review.']}
    result = {'case_id': case_id, 'measured_values': measurement,
              'target_checks': [{'target': 'original speed-zone passage',
                                 'requested': config['case']['draft_variables'],
                                 'measured': measurement, 'method': 'measure_original',
                                 'tolerance': None, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'original physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {},
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
        raise ValueError('refusing to overwrite prior speed-zone analysis report')
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
