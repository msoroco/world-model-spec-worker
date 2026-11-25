"""Measure a source-hashed sight-opening stop diagnostic without a legal verdict."""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(root, case_id):
    root = Path(root)
    manifest = json.loads((root / 'diagnostic-source-manifest.json').read_text())
    if manifest.get('case_id') != case_id or manifest.get('source_kind') not in ('synthetic_native_sample', 'native_observation'):
        raise ValueError('Sight source identity differs')
    needed = ('road.xodr', 'native_samples.jsonl', 'sight_samples.jsonl', 'video_frames.jsonl')
    for name in needed:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    if any(manifest.get('sha256', {}).get(name) != sha(root / name) for name in needed):
        raise ValueError('Sight source hash differs')
    road = ET.parse(root / 'road.xodr').getroot()
    objects = road.findall('.//object')
    if any(item.get('type') == 'crosswalk' or item.get('name') == 'clearly_marked_stop_line' for item in objects):
        raise ValueError('Higher-priority stopping reference present')
    ego, sight, mapping = (rows(root / name) for name in needed[1:])
    if not len(ego) == len(sight) == len(mapping) == 600:
        raise ValueError('Sight source lacks 600 joined frames')
    first_open = None
    first_entry = None
    halted = set()
    for index, (subject, view, frame) in enumerate(zip(ego, sight, mapping)):
        if not (subject.get('native_frame') == view.get('native_frame') == frame.get('carla_frame') and
                subject.get('video_frame') == frame.get('video_frame') == index and
                abs(subject.get('time_s') - view.get('time_s')) < 1e-4 and
                len(subject.get('body_vertices_m', [])) == 8 and
                subject.get('lane_id') == -1 and view.get('approaching_traffic') is True):
            raise ValueError('Sight frame, actor or body join differs')
        eye = view.get('observer_eye_xy_m')
        actor = view.get('intersecting_actor_xy_m')
        bounds = view.get('occluder_xy_bounds_m')
        if (not isinstance(eye, list) or not isinstance(actor, list) or
                not isinstance(bounds, list) or len(bounds) != 4 or
                len(eye) != 2 or len(actor) != 2 or
                not all(isinstance(value, (int, float)) and math.isfinite(value)
                        for value in (*eye, *actor, *bounds)) or
                not bounds[0] < bounds[1] or not bounds[2] < bounds[3] or
                abs(eye[0] - sum(vertex[0] for vertex in subject['body_vertices_m']) / 8) > 1e-6 or
                abs(eye[1] - sum(vertex[1] for vertex in subject['body_vertices_m']) / 8) > 1e-6 or
                actor[0] >= -7 or actor[0] == eye[0]):
            raise ValueError('Sight observer, actor or occluder source differs')
        if manifest['source_kind'] == 'native_observation' and (
                view.get('view_source_kind') != 'native_actor_ray_proxy' or
                not isinstance(view.get('intersecting_actor_id'), int) or
                not isinstance(view.get('occluder_actor_id'), int) or
                view.get('intersecting_actor_velocity_x_mps', 0) <= 0):
            raise ValueError('Original intersecting actor or occluder observation missing')
        def at_x(x):
            return eye[1] + (x - eye[0]) / (actor[0] - eye[0]) * (actor[1] - eye[1])
        low, high = sorted((at_x(bounds[0]), at_x(bounds[1])))
        occluded = high >= bounds[2] and low <= bounds[3]
        if view.get('view_open') is not (not occluded):
            raise ValueError('Sight ray/occluder computation differs')
        front = max(vertex[1] for vertex in subject['body_vertices_m'])
        if view.get('view_open') is True and first_open is None:
            first_open = index
        if front >= -7 and first_entry is None:
            first_entry = index
        if subject.get('speed_mps', 99) <= 0.15:
            halted.add(index)
    if first_open is None or first_entry is None or first_open >= first_entry:
        raise ValueError('Sight opening before intersection not established')
    run = best = 0
    for index in range(first_open, first_entry):
        run = run + 1 if index in halted else 0
        best = max(best, run)
    return {'format': 'c111325-sight-point-source-measurement-v1',
            'case_id': case_id, 'source_kind': manifest['source_kind'],
            'source_hashes': {name: sha(root / name) for name in needed},
            'first_view_open_frame': first_open,
            'first_intersection_body_frame': first_entry,
            'longest_halt_after_view_open_frames': best,
            'halt_at_view_point_observed': best >= 20,
            'view_source_kind': sight[first_open].get('view_source_kind'),
            'original_pixel_reviewed': False,
            'physical_visibility_verified': False,
            'legal_verdict': None}
