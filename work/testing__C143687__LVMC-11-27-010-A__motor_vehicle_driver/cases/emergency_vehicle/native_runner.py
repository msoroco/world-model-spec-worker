"""Native trail acquisition with reviewed source sidecar and local cleanup.

The sidecar is selected by C143687_REVIEWED_SOURCE_DIR and must contain a
reviewed site.json, packet.json and every packet source. It is copied into the
fresh attempt before CARLA starts. No diagnostic site is eligible for Native.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from native_route_control import command as route_command
from source_packet import verify_packet
from trail import CASES, build_case, validate_source
from trail_capture import capture as capture_trail
from trail_video import FourVideoRecorder


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


class TraceCapture:
    """Append source frame identities and original vehicle XY during acquisition."""

    def __init__(self, path):
        self.stream = Path(path).open('x', encoding='utf-8', buffering=1)

    def capture(self, frame, time_s, location_xy, case_id):
        row = {'frame': frame, 'time_s': time_s, 'position_m':
               [location_xy[0], location_xy[1], 0.0], 'case_id': case_id}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        return row

    def close(self):
        self.stream.close()


def reviewed_source(source_dir, case_id):
    root = Path(source_dir).resolve()
    site_path, packet_path = root / 'site.json', root / 'packet.json'
    if not site_path.is_file() or not packet_path.is_file():
        raise ValueError('reviewed original site and packet missing')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if site.get('provenance_kind') != 'reviewed_original' or site.get('case_id') != case_id:
        raise ValueError('reviewed original site provenance or exact case missing')
    suffix = case_id.rsplit('__', 1)[-1]
    case = next((item for item in CASES if item.name == suffix), None)
    if case is None:
        raise ValueError('unknown exact trail case')
    validate_source(site, case)
    verify_packet(site, packet_path)
    sign = site['sign']
    if not sign.get('native_blueprint') or type(sign.get('face_yaw_deg')) not in (int, float):
        raise ValueError('reviewed Native sign asset or face orientation missing')
    if not math.isfinite(sign['face_yaw_deg']) or not site.get('operator_id'):
        raise ValueError('reviewed Native sign face or operator identity missing')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    map_path = (root / packet['sources']['map']['path']).resolve()
    if root not in map_path.parents or _sha(map_path) != site['map_sha256']:
        raise ValueError('reviewed OpenDRIVE map source missing')
    return site, case, map_path


class CarlaAdapter:
    def __init__(self, world, carla, site):
        self.world, self.carla, self.site = world, carla, site
        self.actors = []

    def install_sign(self, position, text, **kwargs):
        sign = self.site['sign']
        blueprint = self.world.get_blueprint_library().find(sign['native_blueprint'])
        if blueprint is None:
            raise ValueError('reviewed Native sign blueprint missing')
        pose = self.carla.Transform(
            self.carla.Location(x=position[0], y=position[1], z=sign.get('spawn_z_m', 0)),
            self.carla.Rotation(yaw=sign['face_yaw_deg']))
        actor = self.world.try_spawn_actor(blueprint, pose)
        if actor is None:
            raise ValueError('physical sign actor spawn failed')
        self.actors.append(actor)
        return actor

    def spawn_vehicle(self, position, blueprint_id, **kwargs):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None:
            raise ValueError('reviewed motor vehicle blueprint missing')
        second = self.site['route_xy'][1]
        yaw = math.degrees(math.atan2(second[1]-position[1], second[0]-position[0]))
        pose = self.carla.Transform(
            self.carla.Location(x=position[0], y=position[1], z=self.site.get('vehicle_spawn_z_m', .5)),
            self.carla.Rotation(yaw=yaw))
        actor = self.world.try_spawn_actor(blueprint, pose)
        if actor is None:
            raise ValueError('motor vehicle spawn failed')
        self.actors.append(actor)
        return actor

    def set_route(self, vehicle, route, **kwargs):
        self.route = route

    def bind_status(self, vehicle, **kwargs):
        self.status = kwargs

    def destroy(self, actor):
        actor.destroy()


def geometric_sign_face_observer(sign_actor, vehicle, site, snapshot):
    """Live actor and face-orientation proxy; actual pixels remain unverified."""
    if not sign_actor.is_alive or snapshot.find(sign_actor.id) is None:
        return False
    if sign_actor.type_id != site['sign']['native_blueprint']:
        return False
    vehicle_location = vehicle.get_transform().location
    sign_location = sign_actor.get_transform().location
    dx, dy = vehicle_location.x - sign_location.x, vehicle_location.y - sign_location.y
    distance = math.hypot(dx, dy)
    if not math.isfinite(distance) or distance > 25:
        return False
    azimuth = math.degrees(math.atan2(dy, dx))
    face = float(sign_actor.get_transform().rotation.yaw)
    error = ((azimuth - face + 180) % 360) - 180
    return abs(error) <= 60


def run_native(bundle, output, reviewed_dir, host='127.0.0.1', port=2000):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    repo = bundle.parents[3]
    scratch = (repo / '.runtime-work').resolve()
    if not output.is_dir() or scratch not in output.parents:
        raise ValueError('fresh materialized attempt must be under .runtime-work')
    config = json.loads((output / 'config.json').read_text(encoding='utf-8'))
    case_id = config['selected_case_id']
    site, case, _ = reviewed_source(reviewed_dir, case_id)
    if (output / 'reviewed_source').exists():
        raise ValueError('reviewed source already copied into attempt')
    shutil.copytree(reviewed_dir, output / 'reviewed_source')
    site, case, map_path = reviewed_source(output / 'reviewed_source', case_id)
    if any((output / name).exists() for name in (
            'trace.jsonl', 'video_frames.jsonl', 'original-history.jsonl', 'acquisition.json')):
        raise ValueError('original acquisition already exists')
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'c143687-native-pipeline')
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    client = carla.Client(host, port)
    client.set_timeout(30)
    previous = snapshot_world(client)
    world = None
    adapter = None
    video = pipeline = frame_map = joins = None
    errors = []
    restoration = {'restored': False}
    count = 0
    try:
        world = client.generate_opendrive_world(map_path.read_text(encoding='utf-8'))
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        adapter = CarlaAdapter(world, carla, site)
        actors = build_case(adapter, site, case)
        vehicle, sign = actors['vehicle'], actors['sign']
        video = FourVideoRecorder(world, site, carla, output)
        pipeline = TraceCapture(output / 'trace.jsonl')
        frame_map = FrameMap(output / 'video_frames.jsonl')
        joins = (output / 'camera-frame-joins.jsonl').open('x', buffering=1)
        camera_plan_sha = hashlib.sha256(json.dumps(config['cameras'], sort_keys=True).encode()).hexdigest()

        def before_tick(actor, source, index):
            route_command(actor, source, carla, index)

        def on_frame(sample, snapshot):
            nonlocal count
            joined = video.append(sample, snapshot)
            graph = pipeline.capture(sample['frame'], sample['time_s'],
                                     sample['location_xy'], case_id)
            if graph['frame'] != sample['frame']:
                raise ValueError('original trace and camera frame differ')
            frame_map.append(sample['frame'], sample['time_s'])
            joins.write(json.dumps(joined, allow_nan=False) + '\n')
            count += 1

        capture_trail(world, vehicle, site['operator_id'],
                      lambda snapshot, face: geometric_sign_face_observer(sign, vehicle, site, snapshot),
                      site, case, output / 'reviewed_source' / 'packet.json',
                      output / 'original-history.jsonl', camera_plan_sha,
                      before_tick=before_tick, on_frame=on_frame)
    except BaseException as error:
        errors.append(repr(error))
    finally:
        for resource in (joins, frame_map, pipeline, video):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        if adapter is not None:
            for actor in reversed(adapter.actors):
                try: actor.destroy()
                except BaseException as error: errors.append(repr(error))
        try: restoration = restore(client, previous)
        except BaseException as error: errors.append('world restoration: ' + repr(error))
    if errors or count != 900 or not restoration.get('restored'):
        _write(output / 'native-run-status.json', {'phase': 'failed', 'errors': errors,
               'frames': count, 'restoration': restoration})
        raise RuntimeError('Native trail acquisition or restoration failed; retain failed attempt')
    sources = {}
    for name in ('site.json', 'packet.json'):
        path = output / 'reviewed_source' / name
        sources[name] = {'path': str(path.relative_to(output)), 'sha256': _sha(path)}
    acquisition = {'case_id': case_id, 'cell_id': 'C143687', 'frame_count': count,
                   'fps': 20, 'provenance_kind': 'original_native', 'diagnostic_fixture': False,
                   'site': sources['site.json'], 'source_packet': sources['packet.json'],
                   'history': {'path': 'original-history.jsonl',
                               'sha256': _sha(output / 'original-history.jsonl')},
                   'packet_stream': {'path': 'original-history-packets.jsonl',
                                     'sha256': _sha(output / 'original-history-packets.jsonl')},
                   'camera_media': {name: {'path': name + '.mkv',
                                          'sha256': _sha(output / (name + '.mkv'))}
                                    for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}}
    _write(output / 'acquisition.json', acquisition)
    seal_capture(output, frames=count, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in acquisition['camera_media']},
                 context={'case_id': case_id, 'reviewed_source_sha256': sources['site.json']['sha256']})
    return {'case_id': case_id, 'frames': count, 'native_acquisition_sealed': True,
            'physical_acceptance_claimed': False}
