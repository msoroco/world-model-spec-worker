"""Retain a Native traffic-control head linked to the ending approach.

An OpenDRIVE signal ID and affected-lane readback are simulated control
provenance. They do not resolve official legal status or subsection 4.
"""

import json
from math import isfinite
from pathlib import Path


def _junction_on_route(waypoint, junction_id):
    pending = [waypoint]
    seen = set()
    for _ in range(24):
        if not pending:
            break
        current = pending.pop(0)
        marker = (current.road_id, current.lane_id,
                  round(current.transform.location.x, 2),
                  round(current.transform.location.y, 2))
        if marker in seen:
            continue
        seen.add(marker)
        junction = current.get_junction() if current.is_junction else None
        if junction is not None and str(junction.id) == str(junction_id):
            return True
        pending.extend(current.next(2.0))
    return False


def select_ending_approach_device(lights, subject_path, junction_id):
    """Fail closed on absent or ambiguous Native affected-lane linkage."""
    approach = subject_path[0]
    candidates = []
    for light in lights:
        opendrive_id = str(light.get_opendrive_id() or '').strip()
        if not opendrive_id:
            continue
        for waypoint in light.get_affected_lane_waypoints():
            if ((waypoint.road_id, waypoint.lane_id) ==
                    (approach.road_id, approach.lane_id) and
                    _junction_on_route(waypoint, junction_id)):
                candidates.append((light, opendrive_id, waypoint))
    identities = {light.id for light, _, _ in candidates}
    if len(identities) != 1:
        raise ValueError('Ending approach needs exactly one governing Native device')
    return candidates[0]


def devices_at_junction(lights, junction_id):
    """Inventory Native signal actors whose affected lanes reach this junction."""
    return [light for light in lights if any(
        _junction_on_route(waypoint, junction_id)
        for waypoint in light.get_affected_lane_waypoints())]


class DeviceSourceRecorder:
    def __init__(self, output, selected, junction_id):
        light, opendrive_id, waypoint = selected
        root = Path(output)
        root.mkdir(parents=True, exist_ok=True)
        self.context = root / 'official_device_context.json'
        self.states = root / 'official_device_states.jsonl'
        if self.context.exists() or self.states.exists():
            raise FileExistsError('Retain prior official-device source')
        self.light = light
        self.context.write_text(json.dumps({
            'format': 'worker-ending-road-original-device',
            'device_id': str(light.id), 'opendrive_signal_id': opendrive_id,
            'affected_road_id': waypoint.road_id,
            'affected_lane_id': waypoint.lane_id,
            'junction_id': str(junction_id),
            'association_method': 'Native affected-lane waypoints and connected junction route',
            'legal_official_status_claimed': False,
            'subsection_4_applicability': None}, indent=2) + '\n')
        self.stream = self.states.open('x')
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or not isfinite(time_s):
            raise ValueError('Invalid official-device Native frame identity')
        if self.previous is not None and (frame != self.previous[0] + 1 or
                                          abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Official-device readback is not joined at 20 Hz')
        state = str(self.light.get_state())
        if not state:
            raise ValueError('Missing original Native device state')
        row = {'frame': frame, 'time_s': time_s,
               'device_id': str(self.light.id), 'native_state': state,
               'value': state}
        self.stream.write(json.dumps(row) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()
