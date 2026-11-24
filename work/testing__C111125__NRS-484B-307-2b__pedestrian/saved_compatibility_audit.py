"""Independent saved diagnostic result join; never a delivery acceptance verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(attempt, receipt_path):
    attempt = Path(attempt).resolve()
    receipt = read(receipt_path)
    if receipt.get('passed') is not True or receipt.get('scope') != 'diagnostic software compatibility only':
        raise ValueError('positive diagnostic compatibility receipt required')
    if not {'negative_case_source', 'native_validation', 'final_decode'} <= set(receipt['checks']):
        raise ValueError('compatibility proof omits required checks')
    result = read(attempt / 'result.json')
    report = read(attempt / 'analysis-report.json')
    if (result['case_id'] != receipt['case_id'] or report['case_id'] != receipt['case_id'] or
            result.get('provenance_kind') != 'synthetic_fixture' or
            result.get('physical_acceptance_claimed') is not False or
            report.get('physical_acceptance_claimed') is not False):
        raise ValueError('saved diagnostic identity or provenance differs')
    for name, expected in receipt['fixture_manifest'].items():
        if name in result['video_references']:
            continue
        if sha(attempt / name) != expected:
            raise ValueError('saved diagnostic source changed: ' + name)
    if sha(attempt / 'analysis-report.json') != receipt['analysis_report_sha256']:
        raise ValueError('selected analysis report changed')
    trace = rows(attempt / result['trace_reference'])
    mapping = rows(attempt / result['video_frame_map_reference'])
    frames = read(attempt / 'frames.json')
    channel = rows(attempt / 'channels/pedestrian_body_center_xy_m.jsonl')
    if not trace or not len(trace) == len(mapping) == len(frames) == len(channel):
        raise ValueError('saved pedestrian frame join incomplete')
    for i, (point, mapped, frame, sample) in enumerate(zip(trace, mapping, frames, channel)):
        if (point['frame'] != frame['frame'] or mapped['carla_frame'] != point['frame'] or
                mapped['video_frame'] != i or abs(point['time_s'] - mapped['time_s']) > 1e-9 or
                abs(point['time_s'] - sample['time_s']) > 1e-9 or
                [sample['value']['x'], sample['value']['y']] != frame['pedestrian_xy']):
            raise ValueError('saved pedestrian frame join differs')
    context = read(attempt / 'contexts/source_provenance.json')['source_provenance']
    if context['kind'] != 'synthetic_fixture':
        raise ValueError('source context conceals synthetic provenance')
    for name, expected in context['source_sha256'].items():
        if sha(attempt / name) != expected:
            raise ValueError('source context hash differs: ' + name)
    if len(result['video_references']) != 4 or any(name not in receipt['fixture_manifest']
                                                    for name in result['video_references']):
        raise ValueError('four original diagnostic cameras required')
    for index, name in enumerate(result['video_references']):
        decoded = read(attempt / f'source-{index}.json')
        if (decoded['passed'] is not True or decoded['frames'] != len(trace) or
                decoded['video_sha256'] != sha(attempt / name) or
                decoded['mapping_sha256'] != sha(attempt / result['video_frame_map_reference'])):
            raise ValueError('original diagnostic camera source changed: ' + name)
        expected = digest({'kind': 'generated-diagnostic-video',
                           'frames': decoded['frames'], 'dimensions': decoded['dimensions'],
                           'fps': 20, 'rgb_sequence_sha256': decoded['rgb_sequence_sha256']})
        if receipt['fixture_manifest'][name] != expected:
            raise ValueError('diagnostic camera pixels differ: ' + name)
    if result['setup_confirmed'] or result['behavior_attempted'] or result['maneuver_completed']:
        raise ValueError('synthetic fixture asserts physical completion')
    return {'format': 'worker-diagnostic-saved-audit', 'case_id': result['case_id'],
            'compatibility_receipt_sha256': sha(receipt_path),
            'frames_joined': len(trace), 'original_cameras': len(result['video_references']),
            'source_hashes_checked': len(receipt['fixture_manifest']),
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.write_text(json.dumps(audit(args.attempt, args.receipt), indent=2) + '\n')
