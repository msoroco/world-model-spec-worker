"""Saved original signal-governance measurement for the 257(1) exception.

An active traffic-control signal changes applicability of this subsection; it
does not itself decide lawful conduct under another provision.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

_nearest_path = Path(__file__).with_name('nearest_view.py')
_nearest_spec = importlib.util.spec_from_file_location('c158196_nearest_for_signal', _nearest_path)
_nearest = importlib.util.module_from_spec(_nearest_spec)
_nearest_spec.loader.exec_module(_nearest)


def measure(packet: dict, attempt: Path) -> dict:
    _nearest.verify_source_bytes(packet, attempt)
    context = packet.get('context', {})
    if context.get('cell_id') != 'C158196' or context.get('law_id') != 'NRS-484B-257-1':
        raise ValueError('wrong exact signal-exception law or cell')
    if context.get('signal_controlling') is not True or context.get('officer_controlling') is not False:
        raise ValueError('active signal and absent officer control must be observed')
    for key in ('marked_stop_line', 'near_side_crosswalk', 'sidewalk_derived_crosswalk'):
        if context.get(key) is not False:
            raise ValueError('fixed nearest-view site geometry differs: ' + key)
    source = packet['sources']['signal_state_readback']['path']
    state = json.loads((Path(attempt) / source).read_text(encoding='utf-8'))
    if (state.get('source_kind') != 'original_native_signal_readback' or
            state.get('device_kind') != 'traffic_control_signal' or
            state.get('governs_ego_approach') is not True):
        raise ValueError('original governing signal readback required')
    frames = packet.get('frames')
    observed = state.get('observed_frame_ids')
    signal_rows = state.get('observed_signal_states')
    if not isinstance(frames, list) or len(frames) < 3 or not isinstance(observed, list):
        raise ValueError('original signal/frame history required')
    first = frames[0].get('frame')
    time = frames[0].get('time_s')
    if type(first) is not int or type(time) not in (int, float) or not math.isfinite(time):
        raise ValueError('original signal frame origin required')
    for index, row in enumerate(frames):
        if (row.get('frame') != first + index or
                type(row.get('time_s')) not in (int, float) or
                abs(row['time_s'] - time - index / 20) > 0.001):
            raise ValueError('original signal/frame 20 Hz join differs')
    if observed != [row['frame'] for row in frames]:
        raise ValueError('governing signal does not span original frame history')
    if (not isinstance(signal_rows, list) or len(signal_rows) != len(frames) or
            any(not isinstance(row, dict) or
                row.get('frame') != frame['frame'] or
                row.get('governs_ego_approach') is not True or
                row.get('state') not in ('red', 'yellow', 'green')
                for row, frame in zip(signal_rows, frames))):
        raise ValueError('original per-frame governing signal state missing')
    return {'signal_governs_ego_approach': True,
            'first_frame': first, 'last_frame': frames[-1]['frame'],
            'frame_count': len(frames),
            'signal_state_source_sha256': packet['sources']['signal_state_readback']['sha256'],
            'observed_signal_states': {state: sum(row['state'] == state for row in signal_rows)
                                       for state in ('red', 'yellow', 'green')},
            'subsection_1_exception_observed': True,
            'legal_conduct_under_other_rules': 'unresolved'}
