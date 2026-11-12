"""Bind reviewed sign/marking findings to original Native and camera sources.

Review labels remain judgments about the cited frames. Synthetic diagnostic
reviews can check the software path but cannot establish a real sign face or
the absence of rendered road markings in a future CARLA run.
"""

import hashlib
import json
from pathlib import Path

from yield_site import validate_authored_site

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive_context(root):
    root = Path(root)
    for name in ('road.xodr', 'road_context.json', 'video_frames.jsonl',
                 'control_inventory.jsonl', 'capture/native_map_facts.json',
                 'rendered_marking_review.json', *CAMERAS):
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    authored = validate_authored_site(root / 'road.xodr')
    native = json.loads((root / 'capture/native_map_facts.json').read_text())
    controls = _rows(root / 'control_inventory.jsonl')
    frames = _rows(root / 'video_frames.jsonl')
    review = json.loads((root / 'rendered_marking_review.json').read_text())
    base = json.loads((root / 'road_context.json').read_text())
    if (not isinstance(native.get('junctions'), list)
            or 158191 not in {item.get('id') for item in native['junctions']}
            or native.get('crosswalk_vertices_m') != []):
        raise ValueError('Native junction or crosswalk inventory differs')
    if not frames or len(controls) != len(frames):
        raise ValueError('Native control inventory does not cover recording')
    ids = [row.get('carla_frame') for row in frames]
    expected_yield = base.get('native_yield_sign_id')
    for control, frame in zip(controls, ids):
        sign = control.get('yield_sign', {})
        if (control.get('frame') != frame or sign.get('actor_id') != expected_yield
                or sign.get('blueprint', '').startswith('traffic.yield') is not True
                or len(sign.get('trigger_vertices_m', [])) < 4
                or control.get('native_crosswalk_vertices_m') != []
                or control.get('competing_controls') != []):
            raise ValueError('Native yield governance or competing-control inventory differs')
    if (review.get('method') != 'original_source_camera_frame_review'
            or not review.get('reviewer')
            or review.get('reviewed_frame_count') != len(frames)
            or review.get('reviewed_carla_frames') != ids
            or review.get('first_carla_frame') != ids[0]
            or review.get('last_carla_frame') != ids[-1]):
        raise ValueError('Incomplete original camera marking/sign review')
    source_hashes = review.get('source_sha256')
    if not isinstance(source_hashes, dict) or source_hashes != {
            name: _sha(root / name) for name in CAMERAS}:
        raise ValueError('Original camera review source hashes differ')
    required = ('yield_sign_face_visible', 'no_stop_line',
                'no_near_crosswalk', 'no_police_direction',
                'no_traffic_signal_control')
    if any(type(review.get(key)) is not bool for key in required):
        raise ValueError('Missing explicit source-camera review findings')
    if not all(review[key] for key in required):
        raise ValueError('Selected yield branch not supported by reviewed camera findings')
    if (base.get('native_map_id') != native.get('map')
            or base.get('intersection_id') != 158191
            or base.get('approach_road_id') != 158190
            or base.get('approach_lane_id') != -1
            or base.get('through_highway_id') != 158195
            or base.get('native_yield_sign_id') != expected_yield):
        raise ValueError('Original road/sign context differs from Native sources')
    return dict(base, no_stop_line=True, no_near_crosswalk=True,
                police_control=False, traffic_signal_control=False,
                sign_governance_source='control_inventory.jsonl + road.xodr',
                marking_inventory_source='capture/native_map_facts.json + rendered_marking_review.json',
                authored_site_sha256=authored['road_sha256'],
                source_review_sha256=_sha(root / 'rendered_marking_review.json'))
