"""Independent source-bound untowed versus towed CPU comparison."""
import argparse
import hashlib
import json
from pathlib import Path


COMMON = ('native_map_id', 'highway_id', 'road_id',
          'outside_business_district', 'caravan_or_motorcade',
          'roadway_polygon_xy_m', 'road_forward_xy')
SOURCES = ('business_district_source', 'caravan_membership_source',
           'route_source', 'lane_source')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def context(root):
    value = json.loads((root / 'road_context.json').read_text())
    for name in SOURCES:
        source = value.get(name, {})
        path = root / source.get('path', '')
        if not path.is_file() or sha(path) != source.get('sha256'):
            raise ValueError('Changed original context source: ' + name)
    return value


def audit(untowed_root, towed_root):
    untowed_root, towed_root = Path(untowed_root), Path(towed_root)
    plain, drawn = context(untowed_root), context(towed_root)
    if any(plain.get(name) != drawn.get(name) for name in COMMON + SOURCES):
        raise ValueError('Fixed highway or source context changed')
    relation_path = towed_root / 'towing-relationship.json'
    relation = json.loads(relation_path.read_text())
    design_path = towed_root / 'towing_design_source.txt'
    if (relation.get('drawing_actor_id') != 1 or relation.get('drawn_actor_id') != 8
            or relation.get('drawn_unit_has_motive_power') is not False
            or relation.get('towing_design_source_sha256') != sha(design_path)
            or drawn.get('towing_relationship_source', {}).get('sha256') != sha(relation_path)
            or drawn.get('towing_design_source', {}).get('sha256') != sha(design_path)):
        raise ValueError('Towing relationship or design source changed')
    plain_rows = rows(untowed_root / 'caravan_history.jsonl')
    drawn_rows = rows(towed_root / 'caravan_history.jsonl')
    if len(plain_rows) != 900 or len(drawn_rows) != 900:
        raise ValueError('Full 900-frame original histories required')
    for index, (left, right) in enumerate(zip(plain_rows, drawn_rows)):
        if (left.get('frame') != right.get('frame')
                or left.get('frame') != index + 100
                or left.get('time_s') != right.get('time_s')
                or left.get('road_id') != right.get('road_id')):
            raise ValueError('Original frame or roadway join changed')
        for key in ('caravan_members', 'entering_vehicle'):
            if left.get(key) != right.get(key):
                raise ValueError('Fixed original participants changed: ' + key)
        if left.get('drawn_units') or left.get('towing_relationship'):
            raise ValueError('Untowed source contains drawn unit')
        units = right.get('drawn_units', [])
        if (len(units) != 1 or units[0].get('actor_id') != 8
                or len(units[0].get('body_vertices_xy_m', [])) != 4
                or right.get('towing_relationship') !=
                {'drawing_actor_id': 1, 'drawn_actor_id': 8}):
            raise ValueError('Towed original frame lacks drawn body or link')
    return {'format': 'worker-c160013-towing-comparison',
            'untowed_frames': 900, 'towed_frames': 900,
            'fixed_context_source_hashes': {name: plain[name]['sha256'] for name in SOURCES},
            'untowed_history_sha256': sha(untowed_root / 'caravan_history.jsonl'),
            'towed_history_sha256': sha(towed_root / 'caravan_history.jsonl'),
            'towing_relationship_sha256': sha(relation_path),
            'towing_design_sha256': sha(design_path),
            'declared_difference': 'one towed drawn unit with an original-frame actor link',
            'physical_acceptance_claimed': False,
            'without_danger_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--untowed', type=Path, required=True)
    parser.add_argument('--towed', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.untowed, args.towed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'untowed_frames': 900, 'towed_frames': 900,
                      'comparison_passed': True}))


if __name__ == '__main__':
    main()
