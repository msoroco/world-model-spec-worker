"""Independent saved-source audit for a marked municipal turning course."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video
from marked_course_measurement import measure

ORIGINALS = ('marked_intersection.json', 'authority_source_original.json',
             'turn_body.jsonl', 'video_frames.jsonl', 'trace.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(case, attempt, processed, *, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    require(entry is not None and entry['kind'] == 'delivery', 'Unknown exact marked-turn case')
    attempt, processed = Path(attempt), Path(processed)
    receipt = json.loads((HERE / entry['saved_processing']['receipt']).read_text())
    report = json.loads((processed / 'v0001/analysis/analysis-report.json').read_text())
    require(receipt['case_id'] == report['case_id'] == case and receipt['passed']
            and receipt['originals_preserved'], 'Wrong saved marked-turn case or originals')
    require(receipt['native_revision']['construction_sha256'] == entry['construction_sha256'],
            'Stale exact marked-turn construction')
    source_hashes = {name: digest(attempt / name) for name in (*ORIGINALS, *VIDEOS)}
    if negative:
        source_hashes['authority_source_original.json'] = '0' * 64
    for name, value in source_hashes.items():
        require(receipt['original_source_hashes'].get(name) == value,
                'Stale or missing original authority source: ' + name)
    measured = measure(attempt, case)
    observed = report['measurements']['original_marked_turn_course']
    require(observed['value'] == measured and observed['sources'] == source_hashes,
            'Saved marked-turn measurement changed from original sources')
    body = rows(attempt / 'turn_body.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    require(len(body) == len(mapping) == len(trace) == measured['frame_count'],
            'Incomplete original marked-turn frame inventory')
    for index, (sample, frame, point) in enumerate(zip(body, mapping, trace)):
        identity = sample['frame'], sample['time_s']
        require((frame['carla_frame'], frame['time_s']) == identity
                and (point['frame'], point['time_s']) == identity
                and frame['video_frame'] == index, 'Original marked-turn frame join differs')
        center = [sum(corner[axis] for corner in sample['corners_xy_m']) / 4
                  for axis in (0, 1)]
        require(hypot(center[0]-point['position_m'][0],
                      center[1]-point['position_m'][1]) < .05,
                'Original marked-turn body/trace pose differs')
    for name in VIDEOS:
        audit_video(attempt / name, len(mapping), mapping_sha256=source_hashes['video_frames.jsonl'])
    require(report.get('physical_acceptance_claimed') is False
            and report.get('legal_acceptance_claimed') is False
            and measured['direction_disobedience_legal_judgment'] is None,
            'Marked-turn software report makes an unsupported finding')
    return {'format': 'worker-marked-delivery-source-audit', 'case_id': case,
            'joined_frames': len(mapping), 'decoded_cameras': list(VIDEOS),
            'authority_source_sha256': source_hashes['authority_source_original.json'],
            'source_integrity_passed': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processed', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.processed,
                           negative=args.negative), indent=2))
