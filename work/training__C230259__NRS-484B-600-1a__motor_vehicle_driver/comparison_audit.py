"""Independent exact-case source comparison; no physical or legal conclusion."""
import argparse
import hashlib
import json
from pathlib import Path

REQUESTS = (8, 12, 16, 20)


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(paths, comparison_id):
    if len(paths) != len(REQUESTS):
        raise ValueError('Comparison requires all four exact cases')
    records = []
    source_kinds = []
    for expected, path in zip(REQUESTS, paths):
        folder = Path(path)
        config = load(folder / 'config.json')
        case = config['case_id']
        if not case.endswith('__' + str(expected)) or config['requested_speed_mps'] != expected:
            raise ValueError('Comparison request/identity differs')
        conditions = rows(folder / 'conditions.jsonl')
        native = rows(folder / 'native_motion.jsonl')
        if len(conditions) != 600 or len(native) != 600:
            raise ValueError('Comparison source duration differs')
        if any(item['native_frame'] != motion['native_frame'] for item, motion in zip(conditions, native)):
            raise ValueError('Comparison source frame join differs')
        kinds = {item['source_kind'] for item in native}
        if len(kinds) != 1 or not kinds <= {'synthetic_native_sample', 'original_native_velocity'}:
            raise ValueError('Comparison source provenance differs')
        source_kinds.extend(kinds)
        if 'original_native_velocity' in kinds and not (folder / 'capture-seal.json').is_file():
            raise ValueError('Original comparison source lacks capture seal')
        context = [(item['road'], item['traffic'], item['weather']) for item in conditions]
        camera = [(v['name'], v['width'], v['height'], v['pose_strategy'], v['fov_deg']) for v in config['cameras']]
        records.append({'case_id': case, 'request_mps': expected, 'context': context,
                        'camera': camera, 'road_sha256': sha(folder / 'road.xodr'),
                        'conditions_sha256': sha(folder / 'conditions.jsonl')})
    first = records[0]
    if len(set(source_kinds)) != 1:
        raise ValueError('Comparison mixes fixture and original sources')
    if any((item['context'] != first['context'] or item['camera'] != first['camera']
            or item['road_sha256'] != first['road_sha256']) for item in records[1:]):
        raise ValueError('Comparison fixed conditions changed')
    return {'format': 'c230259-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': [item['case_id'] for item in records],
            'requests_mps': list(REQUESTS), 'fixed_conditions_checked':
            ['road source', 'traffic source', 'weather source', 'camera profile', 'source frame joins'],
            'source_hashes': {item['case_id']: item['conditions_sha256'] for item in records},
            'diagnostic_fixture': source_kinds[0] == 'synthetic_native_sample',
            'physical_comparison_complete': False,
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.comparison)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'cases': len(result['case_ids']),
                      'physical_comparison_complete': False}))


if __name__ == '__main__':
    main()
