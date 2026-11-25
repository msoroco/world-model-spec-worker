"""Exercise three authored towing spacing plans and geometry rejection."""
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from caravan_entry import plan_entry
from caravan_spacing_geometry import plan


def box(x, y):
    return [[x - 1, y - 1], [x + 1, y - 1],
            [x + 1, y + 1], [x - 1, y + 1]]


def run():
    construction = json.loads((PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json').read_text())
    packet = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'site_packet.json'))
    results = []
    for spacing, expected in ((3, 'stop_before'), (10, 'occupy'), (6.5, 'occupy')):
        variant, summary = plan(packet, spacing)
        if summary['planned_outcome'] != expected:
            raise ValueError('Unexpected finite spacing outcome')
        members = [{'actor_id': index + 1,
                    'body_vertices_xy_m': box(row['transform']['x'], row['transform']['y'])}
                   for index, row in enumerate(variant['caravan_vehicles'])]
        entrant = variant['entering_vehicle']['transform']
        route = plan_entry(variant, members, box(entrant['x'], entrant['y']),
                           gap_index=variant['selected_gap_index'], outcome=expected)
        if route['outcome'] != expected or route['actual_occupancy_confirmed']:
            raise ValueError('Planned entry changed actual-motion boundary')
        results.append(summary)
    try:
        plan(packet, 90)
    except ValueError as exc:
        if 'leaves sourced road' not in str(exc):
            raise
    else:
        raise AssertionError('Off-road caravan geometry accepted')
    try:
        plan(packet, 0)
    except ValueError as exc:
        if 'positive member center spacing' not in str(exc):
            raise
    else:
        raise AssertionError('Zero spacing accepted')
    output = PACKAGE / 'cases/towing-sweep-geometry.json'
    output.write_text(json.dumps({'format': 'worker-towing-sweep-geometry-diagnostic',
                                  'points': results, 'negative_off_road_rejected': True,
                                  'negative_zero_spacing_rejected': True,
                                  'native_motion_verified': False,
                                  'legal_judgment': 'unresolved'}, indent=2) + '\n')
    print(json.dumps({'points': len(results), 'off_road_rejected': True,
                      'zero_spacing_rejected': True}))


if __name__ == '__main__':
    run()
