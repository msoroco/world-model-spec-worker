"""Independently audit saved diagnostic arrow cases and decoded camera pixels."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_measurement import measure_saved
from permission_applicability import validate as validate_permission_review

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt: Path, case_id: str):
    attempt = Path(attempt)
    source_path = attempt / 'pedestrian-source.json'
    if not source_path.is_file():
        raise ValueError('Missing required source: pedestrian-source.json')
    source = json.loads(source_path.read_text())
    if source.get('case_id') != case_id:
        raise ValueError('wrong exact pedestrian case source')
    if source.get('diagnostic_fixture') is not True:
        review_ref = source.get('permission_review_ref')
        if review_ref is None:
            raise ValueError('original cited-device permission review missing')
        validate_permission_review(attempt, source['site_ref'], review_ref)
    provenance_path = attempt / 'acquisition-provenance.json'
    if not provenance_path.is_file():
        raise ValueError('acquisition provenance missing')
    provenance = json.loads(provenance_path.read_text())
    diagnostic = (provenance.get('diagnostic_fixture') is True and
                  provenance.get('provenance_kind') == 'synthetic_fixture')
    if (source.get('diagnostic_fixture') is True) != diagnostic:
        raise ValueError('diagnostic source and acquisition provenance differ')
    for ref in (source['site_ref'], source['events_ref'], source['frame_map_ref']):
        path = (attempt / ref['path']).resolve()
        if not path.is_relative_to(attempt.resolve()) or not path.is_file() or sha(path) != ref['sha256']:
            raise ValueError('original pedestrian source hash differs')
    events = json.loads((attempt / source['events_ref']['path']).read_text())
    measured = measure_saved(attempt, source['site_ref'], source['events_ref'],
                             case_id, len(events))
    measured.pop('legal_verdict', None)
    result = json.loads((attempt / 'result.json').read_text())
    report = json.loads((attempt / 'analysis-report.json').read_text())
    if (result.get('case_id') != case_id or result.get('measured_values') != measured or
            report.get('case_id') != case_id or result.get('setup_confirmed') is not False or
            result.get('maneuver_completed') is not False):
        raise ValueError('saved analysis changed original observation or physical scope')
    trace = rows(attempt / 'trace.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    native = rows(attempt / 'capture/native/frames.jsonl')
    if len(events) < 3 or any(len(part) != len(events) for part in
                              (trace, mapping, evidence, native)):
        raise ValueError('saved Native and camera frame counts differ')
    for index, (event, telemetry, video, proof, frame) in enumerate(zip(
            events, trace, mapping, evidence, native)):
        original = index + 1
        time = event['sim_time_seconds']
        if (event['frame'] != index or telemetry['frame'] != original or
                video['carla_frame'] != original or video['native_frame'] != original or
                video['video_frame'] != index or proof['original_frame'] != original or
                proof['replay_frame'] != original or frame['frame'] != original or
                abs(telemetry['time_s'] - time) > 1e-6 or
                abs(video['time_s'] - time) > 1e-6 or
                abs(proof['recording_time_s'] - time) > 1e-6 or
                abs(frame['simulation_time'] - time) > 1e-6):
            raise ValueError('original pedestrian event/frame join differs')
        if not (attempt / 'capture/native' / frame['adapter_graph']).is_file():
            raise ValueError('original adapter graph missing')
    decoded = {}
    for name in VIDEOS:
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                   '-i', str(attempt / name), '-f', 'framemd5', '-']
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if process.returncode:
            raise ValueError('source video pixel decode failed: ' + name)
        pixels = [line for line in process.stdout.splitlines()
                  if line and not line.startswith('#')]
        if len(pixels) != len(events):
            raise ValueError('source video frame count differs: ' + name)
        decoded[name] = hashlib.sha256('\n'.join(pixels).encode()).hexdigest()
    return {'format': 'c109171-independent-diagnostic-delivery-v1',
            'case_id': case_id, 'frame_count': len(events),
            'source_sha256': {'pedestrian-source.json': sha(source_path),
                              'site.json': source['site_ref']['sha256'],
                              'original_events.json': source['events_ref']['sha256']},
            'decoded_rgb_streams': decoded, 'source_join_checked': True,
            'physical_completion_checked': True,
            'physical_completion_status': 'unverified_synthetic_fixture',
            'diagnostic_fixture': diagnostic,
            'statutory_permission': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case_id)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
