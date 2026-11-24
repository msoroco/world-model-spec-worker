"""CPU fake of the complete source capture, Core publication and conversion path."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS

from PIL import Image

from native_capture import capture
from native_publication import project, encode
from native_seal import seal

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__near_centerline'


class Vector(NS):
    pass


class Transform:
    def __init__(self, x):
        self.location = Vector(x=x, y=0.0, z=0.0)
        self.rotation = NS(pitch=0.0, yaw=0.0, roll=0.0)

    def get_forward_vector(self):
        return Vector(x=1.0, y=0.0, z=0.0)


class Ego:
    id = 7
    type_id = 'vehicle.test'
    is_alive = True

    def __init__(self, world):
        self.world = world
        self.bounding_box = NS(location=Vector(x=0.0, y=0.0, z=0.0),
                               extent=Vector(x=1.0, y=1.0, z=0.5),
                               get_world_vertices=self.vertices)

    def get_transform(self):
        return Transform(self.world.frame / 10)

    def get_velocity(self):
        return Vector(x=2.0, y=0.0, z=0.0)

    def vertices(self, transform):
        x = transform.location.x
        return [Vector(x=x + dx, y=dy, z=dz)
                for dx in (-1.0, 1.0) for dy in (-1.0, 1.0)
                for dz in (-0.5, 0.5)]


class World:
    def __init__(self):
        self.frame = 0
        self.ego = Ego(self)

    def get_snapshot(self):
        return NS(frame=self.frame,
                  timestamp=NS(elapsed_seconds=10 + self.frame / 20))

    def get_actors(self):
        return [self.ego]


class Adapter:
    def __init__(self, output, images):
        self.world = World()
        self.output = output
        self.images = images
        self.stopped = self.destroyed = False

    def spawn_ego(self, blueprint, map_name, case_id):
        if blueprint != 'vehicle.test' or case_id != CASE:
            raise ValueError('fake Native identity differs')
        return self.world.ego

    def configure_cameras(self, ego, channels, fps):
        if list(channels) != ['dash', 'front', 'left', 'right'] or fps != 20:
            raise ValueError('fake camera profile differs')

    def resolve_waypoint(self, waypoint_id):
        return [waypoint_id / 10, 0]

    def apply_control(self, ego, command):
        pass

    def tick(self):
        self.world.frame += 1
        return self.world.frame

    def ego_snapshot(self, ego, frame):
        x = frame / 10
        phase = ('approach' if frame < 100 else 'intersection_entry'
                 if frame == 100 else 'turning' if frame < 400 else 'departure')
        return {'case_id': CASE, 'frame': frame, 'phase': phase,
                'road_id': 4 if frame >= 400 else 3 if frame >= 100 else 1,
                'driver_control': True, 'position_xy_m': [x, 0.0],
                'body_corners_xy_m': [[x - 1, -1], [x + 1, -1],
                                      [x - 1, 1], [x + 1, 1]],
                'heading_rad': 0.0, 'speed_mps': 2.0,
                'elapsed_seconds': 10 + frame / 20}

    def camera_frame(self, channel, frame):
        path = self.output / 'original-cameras' / channel / f'{frame:08d}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.images[channel])
        return {'frame': frame, 'channel': channel,
                'source_path': str(path.relative_to(self.output)),
                'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def emergency_stop(self, ego):
        self.stopped = True

    def destroy(self, ego):
        self.destroyed = True


def run(scratch):
    scratch = Path(scratch).resolve()
    if '.runtime-work' not in scratch.parts or scratch.exists():
        raise ValueError('fresh launch proof scratch under .runtime-work required')
    scratch.mkdir(parents=True)
    output = scratch / 'attempt'
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'materialize', '--manifest', str(ROOT / 'execution-manifest.json'),
               '--case', CASE, '--output', str(output)]
    subprocess.run(command, cwd=REPO, check=True, capture_output=True,
                   env=os.environ)
    donor = json.loads((REPO / 'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
                        / 'cases/near_centerline/diagnostic.json').read_text())
    source = scratch / 'reviewed-map.xodr'
    source.write_text(donor['files']['road.xodr'])
    survey = {'cell_id': 'C109705', 'maneuver': 'left_turn',
              'map_name': 'cpu-fake-world', 'map_source_path': source.name,
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'intersecting_roads': [], 'approach_road_id': 1,
              'connector_road_id': 3, 'destination_road_id': 4,
              'destination_centerline_kind': 'mapped',
              'destination_centerline_xy_m': [[0, 0], [0, 10]],
              'destination_half_width_m': 4.2,
              'left_turn_route_waypoint_ids': [10, 11, 12, 13],
              'ego_blueprint_id': 'vehicle.test',
              'camera_plan': ['dash', 'front', 'left', 'right'],
              'approach_policy': 'fixed-route',
              'phase_regions': {'intersection_entry': [[-5, -5], [5, -5],
                                                        [5, 5], [-5, 5]]}}
    for road_id in (1, 4):
        review = {'road_id': road_id, 'highway_status': 'source_verified',
                  'alley': False, 'reviewer': 'CPU fake',
                  'source_citation': 'diagnostic CPU source'}
        review_path = scratch / f'road-{road_id}-review.json'
        review_path.write_text(json.dumps(review) + '\n')
        survey['intersecting_roads'].append({
            'road_id': road_id, 'alley': False,
            'highway_review_status': 'source_verified',
            'public_highway_source': {'path': review_path.name,
                                      'sha256': hashlib.sha256(review_path.read_bytes()).hexdigest()},
            'permitted_lanes': [{'from_xy_m': [0, -10], 'to_xy_m': [0, 0]},
                                {'from_xy_m': [2, 0], 'to_xy_m': [2, -10]}]
            if road_id == 1 else
            [{'from_xy_m': [-10, 0], 'to_xy_m': [0, 0]},
             {'from_xy_m': [0, 2], 'to_xy_m': [-10, 2]}]})
    survey_path = scratch / 'survey.json'
    survey_path.write_text(json.dumps(survey) + '\n')
    survey_sha = hashlib.sha256(survey_path.read_bytes()).hexdigest()
    sizes = {'dash': (1920, 1080), 'front': (1280, 720),
             'left': (1280, 720), 'right': (1280, 720)}
    images = {}
    for channel, size in sizes.items():
        stream = io.BytesIO()
        Image.new('RGB', size, (10, 20, 30)).save(stream, format='PNG')
        images[channel] = stream.getvalue()
    adapter = Adapter(output, images)
    receipt = capture(adapter, CASE, survey, source, output)
    if not adapter.stopped or not adapter.destroyed:
        raise ValueError('fake Native actor cleanup missing')
    receipt.update(seal(output, case_id=CASE, survey_path=survey_path,
                        survey_sha256=survey_sha, map_source_path=source,
                        capture_receipt=receipt))
    (output / 'acquisition.json').write_text(json.dumps(receipt) + '\n')
    (output / 'carla_recorder.log').write_bytes(b'CPU fake recorder source\n')
    recorder = output / 'capture/recorder_info.txt'
    recorder.parent.mkdir(parents=True, exist_ok=True)
    recorder.write_text('Create 7: vehicle.test\n')
    frames = project(output, survey)
    videos = encode(output)
    from worker_exchange.native_output import seal_capture
    sealed = seal_capture(output, frames=frames,
                          restoration={'restored': True, 'method': 'CPU fake world cleanup'},
                          errors=[], encoder_exit_codes={name: 0 for name in videos})
    if sealed['events'] != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Native seal ordering differs')
    converted = scratch / 'converted'
    process = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'process', '--attempt', str(output), '--output', str(converted),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck')]
    completed = subprocess.run(process, cwd=REPO, env=os.environ,
                               capture_output=True, text=True)
    if completed.returncode:
        raise ValueError('Core conversion failed: ' + completed.stderr[-1200:])
    print(json.dumps({'fake_native_frames': frames,
                      'source_graphs': len(list((output / 'graphs/abstract').glob('*.adapter.json'))),
                      'original_camera_videos': sorted(videos),
                      'core_converted': True,
                      'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', required=True)
    args = parser.parse_args()
    run(args.scratch)
