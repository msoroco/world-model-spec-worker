"""Independent source and media checks for exact saved crosswalk deliveries."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(case, attempt, processed, diagnostic=False):
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    if case not in {e['case_id'] for e in manifest['cases']}:
        raise ValueError('unknown exact delivery case')
    attempt, processed = Path(attempt).resolve(), Path(processed).resolve()
    receipt = json.loads((processed / 'processing.json').read_text())
    result_path = processed / 'analysis/result.json'
    result = json.loads(result_path.read_text())
    if (receipt.get('case_id') != case or receipt.get('passed') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('timestamp_joins', {}).get('passed') is not True or
            receipt.get('result_sha256') != sha(result_path) or
            receipt.get('final_video_checks', {}).get('passed') is not True or
            result.get('case_id') != case):
        raise ValueError('saved processing receipt changed or incomplete')
    for name, expected in receipt['original_source_hashes'].items():
        path = attempt / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('original acquisition missing or changed: ' + name)
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    if len(frames) != len(trace) or any(row['frame'] != frame['carla_frame'] or
            abs(row['time_s'] - frame['time_s']) > 1e-6 for row, frame in zip(trace, frames)):
        raise ValueError('original frame/time join differs')
    capture = attempt / 'capture'
    for name in ('site.json', 'ego.json', 'pedestrian.json', 'exception_review.json',
                 'camera_manifest.json', 'frame_map.json'):
        if not (capture / name).is_file():
            raise ValueError('original participant/site/camera source missing: ' + name)
    source_index = json.loads((capture / 'source-index.json').read_text())
    if source_index.get('case_id') != case:
        raise ValueError('original source index selects another case')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit
    decoded = {name: audit(attempt / (name + '.mkv'), len(frames),
                           mapping_sha256=sha(attempt / 'video_frames.jsonl'))
               for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}
    if not all(row['passed'] for row in decoded.values()):
        raise ValueError('original camera pixel decode failed')
    if diagnostic:
        if result.get('provenance_kind') != 'synthetic_fixture' or result.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic provenance differs')
    else:
        if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
            raise ValueError('Native original source required')
        if result['physical_checks']['maneuver']['status'] != 'met':
            raise ValueError('original physical maneuver incomplete')
        if len(frames) != 600:
            raise ValueError('full 30 second Native frame history required')
    return {'format': 'c111610-independent-delivery-cpu-v1', 'case_id': case,
            'joined_frames': len(frames), 'camera_rgb_sha256': {k: v['rgb_sequence_sha256'] for k, v in decoded.items()},
            'source_index_sha256': sha(capture / 'source-index.json'),
            'software_checks_passed': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.attempt, args.processed, args.diagnostic), indent=2))
