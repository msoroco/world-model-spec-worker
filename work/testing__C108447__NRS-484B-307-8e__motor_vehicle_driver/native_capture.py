"""Record original Native observations for a property bypass attempt.

This is an injectable CPU interface: callers supply the exclusive Native world,
ego actor, signal observer and reviewed map packet. It does not infer parcel
status, signal orientation, or avoidance purpose from a route label.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

from route_controller import steering_command, validate_route


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xy(actor: Any) -> tuple[float, float]:
    location = actor.get_location()
    return float(location.x), float(location.y)


def _speed(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.hypot(float(velocity.x), float(velocity.y))


def _signal(observer: Callable[[int, str], dict[str, Any]], frame: int, name: str) -> dict[str, Any]:
    sample = dict(observer(frame, name))
    _require(sample.get('device_id') and sample.get('source') and isinstance(sample.get('facing_ego'), bool), f'{name} source, identity, orientation required')
    _require(sample.get('state') in ('red_alone', 'red_combined', 'yellow', 'green', 'dark', 'unknown'), f'{name} original state required')
    sample['frame'] = frame
    return sample


def capture(
    *, world: Any, ego: Any, map_packet: dict[str, Any], property_id: str,
    case_id: str, purpose: dict[str, Any], actor_source: dict[str, Any],
    signal_observer: Callable[[int, str], dict[str, Any]],
    destination_street_id: str, output: Path, ticks: int = 900,
    waypoint_tolerance_m: float = 1.5,
) -> dict[str, Any]:
    """Drive one 20 Hz episode and write observed route/phase source, or fail closed.

    The caller owns world settings and sensors and must save their Native frame map.
    A successful return means only that this source was recorded, not that the
    property route or statutory conditions physically occurred.
    """
    _require(20 <= ticks <= 2400, 'bounded 20 Hz episode required')
    _require(0 < waypoint_tolerance_m <= 3, 'finite route tolerance required')
    _require(purpose.get('source') and purpose.get('value') in ('avoid_red', 'other', 'unknown'), 'separate purpose source required')
    _require(actor_source.get('source') and actor_source.get('class') == 'vehicle', 'original vehicle class source required')
    _require(destination_street_id == map_packet.get('intersecting_street_id'), 'destination street source join required')
    route = validate_route(map_packet, property_id)
    _require(map_packet.get('coordinate_frame'), 'map coordinate frame required')
    _require(output.suffix == '.json' and output.parent.is_dir(), 'existing text output directory required')
    samples: list[dict[str, Any]] = []
    waypoint = 1
    entry_frame: int | None = None
    first_approach: dict[str, Any] | None = None
    approach_history: list[dict[str, Any]] = []
    destination_history: list[dict[str, Any]] = []
    last_destination: dict[str, Any] | None = None
    try:
        for _ in range(ticks):
            frame = int(world.tick())
            _require(not samples or frame > samples[-1]['frame'], 'Native frames must increase')
            location = _xy(ego)
            speed = _speed(ego)
            yaw = math.radians(float(ego.get_transform().rotation.yaw))
            _require(all(math.isfinite(v) for v in (*location, speed, yaw)), 'finite Native body sample required')
            sample = {'frame': frame, 'time_s': frame / 20.0, 'x': location[0], 'y': location[1], 'speed_mps': speed, 'yaw_rad': yaw}
            samples.append(sample)
            approach = _signal(signal_observer, frame, 'approach_signal')
            destination = _signal(signal_observer, frame, 'destination_signal')
            approach_history.append(approach)
            destination_history.append(destination)
            if first_approach is None:
                first_approach = approach
            last_destination = destination
            if math.dist(location, route[-1]) <= waypoint_tolerance_m:
                entry_frame = frame
                break
            if math.dist(location, route[waypoint]) <= waypoint_tolerance_m and waypoint < len(route) - 1:
                waypoint += 1
            command = steering_command(location, yaw, route[waypoint], speed)
            ego.apply_control(command)
        _require(entry_frame is not None, 'destination street entry not observed')
        _require(len(samples) >= 2, 'ordered Native body route required')
        trace = {
            'format': 'original-native-property-route-v1', 'case_id': case_id,
            'coordinate_frame': map_packet['coordinate_frame'],
            'actor_class': 'vehicle', 'actor_source': actor_source,
            'ego': samples, 'approach_signal': first_approach,
            'destination_signal': last_destination,
            'approach_signal_history': approach_history,
            'destination_signal_history': destination_history,
            'destination_street_id': destination_street_id,
            'destination_entry_frame': entry_frame, 'purpose': purpose,
            'status': 'recorded_unreviewed',
        }
        output.write_text(json.dumps(trace, indent=2, sort_keys=True) + '\n')
        return {'case_id': case_id, 'trace_path': str(output), 'trace_sha256': _sha(output),
                'first_frame': samples[0]['frame'], 'last_frame': entry_frame,
                'sample_count': len(samples), 'physical_acceptance_claimed': False}
    finally:
        ego.apply_control({'steer': 0.0, 'throttle': 0.0, 'brake': 1.0})
