"""Per-frame source-bound recording views for the exact walking-side cases."""

import json
import math
from pathlib import Path

from walking_side import FRAMES, measure


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_channels(attempt, context, walking, trace):
    if len(walking) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Incomplete source window for recording channels')
    measured = measure(context, walking)['measurements']
    out = Path(attempt) / 'channels'
    out.mkdir(exist_ok=True)
    names = ('kin.position', 'kin.speed', 'ru.subject', 'st.sidewalk',
             'st.highway', 'rel.occupies', 'kin.heading',
             'st.lane_direction', 'rel.oncoming')
    values = {name: [] for name in names}
    for source, original, item in zip(walking, trace, measured):
        if source['native_frame'] != original['frame'] or source['time_s'] != original['time_s']:
            raise ValueError('Recording channel source/frame join differs')
        heading = source['pedestrian_heading_xy']
        frame_values = {
            'kin.position': original['position_m'],
            'kin.speed': original['speed_mps'],
            'ru.subject': source['pedestrian_id'],
            'st.sidewalk': {'provided': context['sidewalk_present'],
                            'inventory_source': context['sidewalk_inventory_source']},
            'st.highway': {'inside_sourced_boundary': item['within_highway_boundary'],
                           'authority_source': context['highway_authority_source'],
                           'boundary_source': context['highway_boundary_source']},
            'rel.occupies': item['highway_side'],
            'kin.heading': math.degrees(math.atan2(heading[1], heading[0])),
            'st.lane_direction': {'direction_xy': context['traffic_direction_xy'],
                                  'route_source': context['traffic_route_source']},
            'rel.oncoming': {'facing_opposite_traffic': item['heading_traffic_dot'] < 0,
                             'approaching_vehicle_ahead': item['approaching_vehicle_ahead']}}
        for name, value in frame_values.items():
            values[name].append({'time_s': original['time_s'], 'value': value})
    for name, expected in values.items():
        path = out / (name + '.jsonl')
        if path.is_file():
            if rows(path) != expected:
                raise ValueError('Recording channel disagrees with original source: ' + name)
        else:
            path.write_text(''.join(json.dumps(row) + '\n' for row in expected))
    return names
