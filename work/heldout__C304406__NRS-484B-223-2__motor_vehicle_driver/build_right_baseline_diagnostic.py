"""Build a textual software fixture for the first three-lane exact case.

The supplied runtime example provides converter-shaped telemetry, graphs and
synthetic camera frames. The lane/body sources below are diagnostic geometry;
they never assert a Native scene or physical/legal outcome.
"""

import json
from pathlib import Path

from three_lane_measurement import CONDITIONS


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def build():
    example = json.loads((ROOT / 'runtime/fixtures/example.json').read_text())
    files = example['files']
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    rows = []
    for source in trace:
        x, y = source['position_m'][:2]
        lane_centers = {'right': y, 'center': y + 3.5, 'extreme_left': y + 7}
        polygons = {name: [[x - 6, cy - 1.75], [x + 6, cy - 1.75],
                           [x + 6, cy + 1.75], [x - 6, cy + 1.75]]
                    for name, cy in lane_centers.items()}
        rows.append({'frame': source['frame'], 'time_s': source['time_s'],
                     'road_id': 1, 'road_travel_tangent_xy': [1, 0],
                     'ego_actor_id': 'synthetic-205',
                     'ego_corners_xy': [[x - 1, y - .7], [x + 1, y - .7],
                                        [x + 1, y + .7], [x - 1, y + .7]],
                     'lane_polygons_xy': polygons})
    context = {name: {'value': None, 'source_ref': None} for name in CONDITIONS}
    context['map_marked_three_lane_candidate'] = {
        'value': True, 'source_ref': 'three_lane_map_readback.json'}
    readback = {'road_id': 1,
                'lane_ids': {'right': -1, 'center': -2, 'extreme_left': 1},
                'lane_widths_m': {name: 3.5 for name in lane_centers},
                'lane_directions_xy': {'right': [1, 0], 'center': [1, 0],
                                       'extreme_left': [-1, 0]},
                'markings': {name: {'left': 'Solid', 'right': 'Solid'}
                             for name in lane_centers},
                'map_markings_verified': True,
                'physical_paint_visible': None, 'legal_lane_status': None}
    files['three_lane_frames.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    files['three_lane_context.json'] = json.dumps(context) + '\n'
    files['three_lane_map_readback.json'] = json.dumps(readback) + '\n'
    return example


def main():
    output = HERE / 'right-baseline-diagnostic.json'
    output.write_text(json.dumps(build(), separators=(',', ':'), allow_nan=False) + '\n')
    print(output)


if __name__ == '__main__':
    main()
