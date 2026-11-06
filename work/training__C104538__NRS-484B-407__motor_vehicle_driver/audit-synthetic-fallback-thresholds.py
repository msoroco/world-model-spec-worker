"""Independent raw-context audit of synthetic C104538 trigger crossings."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((HERE / 'synthetic-fallback-threshold-summary.json').read_text())
    assert receipt['source_kind'] == 'synthetic_cpu_fixture'
    assert not any(receipt[key] for key in ('original_native_observed', 'original_pixel_observed', 'selected'))
    root = REPO / receipt['source_dir']
    expected = {'baseline': (False, False), 'crest_error': (True, False),
                'barrier_gap': (False, True)}
    assert set(receipt['cases']) == set(expected) | {'source_corrupt'}
    original_map = sha(root / 'baseline/native_road_readback.xodr')
    for label, flags in expected.items():
        directory = root / label
        row = receipt['cases'][label]
        context_path = directory / 'native-construction-context.json'
        context = json.loads(context_path.read_text())
        assert sha(context_path) == row['context_sha256']
        assert sha(directory / 'native_road_readback.xodr') == original_map == row['map_sha256']
        heights = context['waypoint_elevation_samples']
        crest = max(abs(item['native_waypoint_z_m'] - item['authored_road_height_m']) for item in heights)
        inventory = context['barrier_inventory']
        assert len(inventory) == 2
        first, second = inventory
        start = [point[0] for point in first['world_vertices_m']]
        end = [point[0] for point in second['world_vertices_m']]
        gap = max(0, min(end) - max(start))
        assert math.isclose(crest, row['maximum_native_crest_height_error_m'], abs_tol=1e-9)
        assert math.isclose(gap, row['maximum_native_barrier_box_gap_m'], abs_tol=1e-9)
        assert (crest > .15, gap > .05) == flags
        assert (row['fallback1_trigger'], row['fallback2_trigger']) == flags
        assert row['fallback3_original_pixel_trigger'] is False
        assert len((directory / 'trace.jsonl').read_text().splitlines()) == 480
    assert receipt['cases']['source_corrupt'] == {
        'rejected': True, 'error': 'Native map readback hash differs'}
    assert sha(root / 'source_corrupt/native_road_readback.xodr') != original_map
    print(json.dumps({'synthetic_cases_audited': 3, 'crossing_fallbacks': 2,
                      'changed_map_rejected': True, 'original_observations': 0}))


if __name__ == '__main__':
    main()
