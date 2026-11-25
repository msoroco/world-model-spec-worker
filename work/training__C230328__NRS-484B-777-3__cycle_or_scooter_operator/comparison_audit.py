"""Independent source-bound two/three-rider contrast; legal judgment stays open."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(root, case):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    context = json.loads((root / 'road_context.json').read_text())
    report = json.loads((root / 'analysis-report.json').read_text())
    poses = [json.loads(line) for line in (root / 'rider_poses.jsonl').read_text().splitlines()]
    if config['case_id'] != case or len(poses) != 600 or any(row['video_frame'] != i for i, row in enumerate(poses)):
        raise ValueError('Incomplete or wrong exact comparison source')
    if any(row['source_kind'] != 'synthetic_native_sample' for row in poses):
        raise ValueError('Comparison provenance changed')
    if report.get('legal_verdict') is not None or context.get('legal_verdict') is not None:
        raise ValueError('Comparison cannot assign legal outcome')
    count = report['source_geometry']['rider_count']
    if count != len(context['rider_ids']) or any(len(row['riders']) != count for row in poses):
        raise ValueError('Measured rider count differs')
    first = report['source_geometry']['per_frame_geometry'][0]['pairwise']
    if len(first) != count * (count - 1) // 2:
        raise ValueError('Pair geometry incomplete')
    fixed = {key: context[key] for key in ('public_dedication_source',
              'public_vehicle_access_source', 'roadway_boundary_source',
              'shoulder_boundary_source', 'exclusive_use_source',
              'exclusive_use_review_source', 'rider_device_source',
              'bicycle_wheel_source', 'bicycle_diameter_source',
              'bicycle_moped_exclusion_source', 'exclusive_use_reviewed')}
    return {'case_id': case, 'requested_rider_count': 2 if case.endswith('__controlled_1') else 3,
            'measured_rider_count': count, 'pair_count_per_frame': len(first),
            'fixed_conditions': fixed, 'source_kind': context['review_kind'],
            'source_hashes': {name: sha(root / name) for name in
                              ('config.json', 'road_context.json', 'rider_poses.jsonl',
                               'video_frames.jsonl', 'analysis-report.json')}}


def audit(root_a, root_b, case_a, case_b, comparison):
    a, b = one(root_a, case_a), one(root_b, case_b)
    if a['fixed_conditions'] != b['fixed_conditions'] or a['source_kind'] != b['source_kind']:
        raise ValueError('Comparison fixed conditions differ')
    if ((a['requested_rider_count'], b['requested_rider_count']) != (2, 3) or
            (a['measured_rider_count'], b['measured_rider_count']) != (2, 3) or
            (a['pair_count_per_frame'], b['pair_count_per_frame']) != (1, 3)):
        raise ValueError('Selected measured rider contrast absent')
    return {'format': 'c230328-independent-comparison-audit-v1',
            'comparison_id': comparison, 'cases': [a, b],
            'deliberate_difference': 'simultaneous lateral rider count',
            'observed_rider_count_delta': 1,
            'diagnostic_fixture': True, 'physical_acceptance': False,
            'legal_verdict': None,
            'limitations': ['Original roadway, exclusive-use status and legal abreast grouping require independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('root-a', 'root-b', 'case-a', 'case-b', 'comparison', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = audit(args.root_a, args.root_b, args.case_a, args.case_b, args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': args.comparison,
                      'observed_rider_count_delta': 1, 'physical_acceptance': False}))
