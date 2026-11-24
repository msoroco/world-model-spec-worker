"""Record original Native observations for a property bypass attempt.

This is an injectable CPU interface: callers supply the exclusive Native world,
ego actor, signal observer and reviewed map packet. It does not infer parcel
status, signal orientation, or avoidance purpose from a route label.
"""
from __future__ import annotations

import hashlib
import json
import math
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from zipfile import ZipFile

from PIL import Image

from route_controller import apply_carla_control, steering_command, validate_roadway_route, validate_route

CAMERAS = ('overview', 'approach', 'property', 'destination')


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
    control_applier: Callable[[Any, dict[str, float]], None] = apply_carla_control,
    camera_observer: Callable[[int, str], bytes] | None = None,
    media_directory: Path | None = None,
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
    route = (validate_roadway_route(map_packet) if case_id.endswith('__ordinary_crossing')
             else validate_route(map_packet, property_id))
    _require(map_packet.get('coordinate_frame'), 'map coordinate frame required')
    settings = world.get_settings()
    _require(settings.synchronous_mode is True and
             type(settings.fixed_delta_seconds) in (int, float) and
             abs(settings.fixed_delta_seconds - 0.05) < 1e-9,
             'synchronous 20 Hz Native world required')
    _require(output.suffix == '.json' and output.parent.is_dir(), 'existing text output directory required')
    _require((camera_observer is None) == (media_directory is None), 'camera observer and media directory must be supplied together')
    if media_directory is not None:
        _require(media_directory.is_dir(), 'existing original media directory required')
    samples: list[dict[str, Any]] = []
    waypoint = 1
    entry_frame: int | None = None
    first_approach: dict[str, Any] | None = None
    approach_history: list[dict[str, Any]] = []
    destination_history: list[dict[str, Any]] = []
    entry_destination: dict[str, Any] | None = None
    frame_rows: list[dict[str, Any]] = []
    camera_members: dict[str, list[dict[str, Any]]] = {name: [] for name in CAMERAS}
    stack = ExitStack()
    archives = {name: stack.enter_context(ZipFile(media_directory / f'{name}.zip', 'w'))
                for name in CAMERAS} if media_directory is not None else {}
    try:
        for index in range(ticks):
            frame = int(world.tick())
            _require(not samples or frame == samples[-1]['frame'] + 1, 'Native frames must increase consecutively')
            snapshot = world.get_snapshot()
            _require(snapshot.frame == frame, 'Native snapshot frame differs from tick')
            time_s = snapshot.timestamp.elapsed_seconds
            _require(type(time_s) in (int, float) and math.isfinite(time_s),
                     'finite original Native timestamp required')
            _require(not samples or abs(time_s - samples[0]['time_s'] - index / 20) < 0.002,
                     'original Native 20 Hz clock drift')
            location = _xy(ego)
            speed = _speed(ego)
            yaw = math.radians(float(ego.get_transform().rotation.yaw))
            _require(all(math.isfinite(v) for v in (*location, speed, yaw)), 'finite Native body sample required')
            sample = {'frame': frame, 'time_s': time_s, 'x': location[0], 'y': location[1], 'speed_mps': speed, 'yaw_rad': yaw}
            samples.append(sample)
            approach = _signal(signal_observer, frame, 'approach_signal')
            destination = _signal(signal_observer, frame, 'destination_signal')
            approach_history.append(approach)
            destination_history.append(destination)
            if camera_observer is not None:
                camera_row: dict[str, dict[str, str]] = {}
                for name in CAMERAS:
                    data = camera_observer(frame, name)
                    _require(isinstance(data, bytes), f'{name} original PNG bytes required')
                    with Image.open(BytesIO(data)) as image:
                        _require(image.format == 'PNG' and image.width > 0 and image.height > 0, f'{name} original PNG required')
                        image.load()
                    member = f'{frame}.png'
                    digest = hashlib.sha256(data).hexdigest()
                    archives[name].writestr(member, data)
                    camera_row[name] = {'member': member, 'sha256': digest}
                    camera_members[name].append({'frame': frame, 'member': member, 'sha256': digest})
                frame_rows.append({'frame': frame, 'time_s': sample['time_s'], 'cameras': camera_row})
            if first_approach is None:
                first_approach = approach
            if entry_frame is None and math.dist(location, route[-1]) <= waypoint_tolerance_m:
                entry_frame = frame
                entry_destination = destination
            if entry_frame is not None:
                control_applier(ego, {'steer': 0.0, 'throttle': 0.0, 'brake': 1.0})
                continue
            if math.dist(location, route[waypoint]) <= waypoint_tolerance_m and waypoint < len(route) - 1:
                waypoint += 1
            command = steering_command(location, yaw, route[waypoint], speed)
            control_applier(ego, command)
        _require(entry_frame is not None, 'destination street entry not observed')
        _require(len(samples) >= 2, 'ordered Native body route required')
        trace = {
            'format': 'original-native-property-route-v1', 'case_id': case_id,
            'coordinate_frame': map_packet['coordinate_frame'],
            'actor_class': 'vehicle', 'actor_source': actor_source,
            'ego': samples, 'approach_signal': first_approach,
            'destination_signal': entry_destination,
            'approach_signal_history': approach_history,
            'destination_signal_history': destination_history,
            'destination_street_id': destination_street_id,
            'destination_entry_frame': entry_frame, 'purpose': purpose,
            'status': 'recorded_unreviewed',
        }
        output.write_text(json.dumps(trace, indent=2, sort_keys=True) + '\n')
        stack.close()
        media = None
        if media_directory is not None:
            frame_path = media_directory / 'frame-map.jsonl'
            frame_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in frame_rows))
            media = {'frame_map': {'path': str(frame_path), 'sha256': _sha(frame_path)},
                     'cameras': {name: {'path': str(media_directory / f'{name}.zip'),
                                        'sha256': _sha(media_directory / f'{name}.zip'),
                                        'frames': camera_members[name]} for name in CAMERAS}}
        return {'case_id': case_id, 'trace_path': str(output), 'trace_sha256': _sha(output),
                'first_frame': samples[0]['frame'], 'last_frame': samples[-1]['frame'],
                'destination_entry_frame': entry_frame,
                'sample_count': len(samples), 'media': media,
                'physical_acceptance_claimed': False}
    finally:
        stack.close()
        control_applier(ego, {'steer': 0.0, 'throttle': 0.0, 'brake': 1.0})
