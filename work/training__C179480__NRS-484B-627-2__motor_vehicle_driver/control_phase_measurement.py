"""Measure a light-state transition from synchronized original actor rows."""
import json
from pathlib import Path

from source_measurement import load_rows


def measure_red_onset(actor_path, frame_map_path, *, expected_control_id,
                      source_kind='original_carla_actor_and_map_readback'):
    rows = load_rows(actor_path, frame_map_path)
    frame_rows = [json.loads(line) for line in Path(frame_map_path).read_text().splitlines()]
    if len(rows) != len(frame_rows):
        raise ValueError('Control phase frame map is incomplete')
    previous = None
    onset = None
    associated_red = 0
    for index, (row, frame) in enumerate(zip(rows, frame_rows)):
        state = row.get('governing_control_state')
        if (not isinstance(state, dict) or state.get('source_kind') != source_kind or
                state.get('control_actor_id') != expected_control_id or
                state.get('control_type_id') != 'traffic.traffic_light' or
                state.get('control_state') not in
                ('TrafficLightState.Green', 'TrafficLightState.Red')):
            raise ValueError('Control phase lacks exact original state or identity')
        inventory = row.get('scene_actor_inventory', {}).get('actors', [])
        lights = [actor for actor in inventory if actor.get('actor_id') == expected_control_id]
        if len(lights) != 1 or lights[0].get('state') != state['control_state']:
            raise ValueError('Control readback and scene inventory disagree')
        if (frame.get('carla_frame') != row['frame'] or frame.get('video_frame') != index or
                type(frame.get('time_s')) not in (int, float)):
            raise ValueError('Control phase frame timing is not joined')
        current = state['control_state'].split('.')[-1]
        if current == 'Red' and previous == 'Green' and onset is None:
            onset = (index, frame['time_s'])
        if (current == 'Red' and state.get('ego_at_control') and
                state.get('ego_associated_control_id') == expected_control_id):
            associated_red += 1
        previous = current
    if onset is None:
        raise ValueError('No source-observed green-to-red transition')
    return {'source_kind': source_kind, 'sample_count': len(rows),
            'control_actor_id': expected_control_id,
            'red_onset_sample': onset[0], 'red_onset_s': onset[1],
            'associated_red_frame_count': associated_red,
            'legal_applicability': 'independent_original_source_review_required',
            'legal_verdict_claimed': False}
