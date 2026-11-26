"""Synthetic original-shaped source comparison; never physical proof."""
import json
from pathlib import Path

from comparison_meter import compare


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c190631-measure-fixtures'
ROAD = SCRATCH / 'roadway'
WALK = SCRATCH / 'sidewalk'


def rejected(call, phrase):
    try:
        call()
    except ValueError as exc:
        if phrase not in str(exc):
            raise
        return str(exc)
    raise AssertionError('Invalid comparison accepted: ' + phrase)


def main():
    road_poses = ROAD / 'pedestrian-poses.jsonl'
    road_geom = ROAD / 'surface-geometry.json'
    walk_poses = WALK / 'pedestrian-poses.jsonl'
    walk_geom = WALK / 'surface-geometry.json'
    positive = compare(road_poses, road_geom, walk_poses, walk_geom)
    wrong_geom = SCRATCH / 'comparison-wrong-geometry.json'
    value = json.loads(walk_geom.read_text())
    value['grade_separation_m'] = 6
    wrong_geom.write_text(json.dumps(value) + '\n')
    negatives = {
        'geometry': rejected(lambda: compare(road_poses, road_geom, walk_poses, wrong_geom),
                             'Compared overpass geometry differs'),
        'surface': rejected(lambda: compare(road_poses, road_geom, road_poses, road_geom),
                            'Walking surface difference not measured'),
        'missing_footprint': rejected(lambda: compare(SCRATCH / 'missing-footprint.jsonl',
                                 road_geom, walk_poses, walk_geom),
                                 'original pedestrian footprint source missing')}
    print(json.dumps({'passed': True, 'positive': positive, 'negatives': negatives},
                     sort_keys=True))


if __name__ == '__main__':
    main()
