"""Stage diagnostic sources for CPU checks or reviewed originals for Native capture."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil

from native_case_bundles import expand
from source_authority import verify as verify_source_authority


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def diagnostic_assets(plan, case_id, variant, map_text):
    """Build plainly synthetic offline sources without implying official authority."""
    reviews = {
        'no-device-review.json': text({'diagnostic_fixture': True, 'device_ids': []}),
        'one-device-review.json': text({'diagnostic_fixture': True, 'device_ids': [8]}),
        'camera-review.json': text({'diagnostic_fixture': True,
                                    'four_views': ['overview', 'approach',
                                                   'reference_corner', 'driver_reference']}),
    }
    offset = 0.0 if variant == 'primary' else 0.2
    base = {'map_source_sha256': hashlib.sha256(map_text.encode()).hexdigest(),
            'fixed_delta_seconds': .05, 'planned_frames': 240,
            'target_xy_m': [15, 6.5], 'speed_mps': 1,
            'walker_spawn_xyz_m': [15 + offset, -6.5, 1],
            'walker_blueprint_id': 'walker.pedestrian.0001',
            'highway_polygon_xy_m': [[0, -5.5], [30, -5.5],
                                     [30, 5.5], [0, 5.5]],
            'route_id': 'synthetic-pedestrian-route', 'facing_head_id': 5,
            'governing_pedestrian_device_ids': [],
            'camera_placements': {name: {'location_xyz_m': [10, -10, 4],
                                         'target_xyz_m': [15, 0, 1]}
                                  for name in ['overview', 'approach',
                                               'reference_corner', 'driver_reference']},
            'camera_placement_review': {
                'complete': True, 'source_path': 'camera-review.json',
                'source_sha256': hashlib.sha256(reviews['camera-review.json'].encode()).hexdigest()},
            'device_inventory_review': {
                'complete': True, 'source_path': 'no-device-review.json',
                'source_sha256': hashlib.sha256(reviews['no-device-review.json'].encode()).hexdigest()},
            'diagnostic_fixture': True}
    one = deepcopy(base)
    one['governing_pedestrian_device_ids'] = [8]
    one['device_inventory_review'] = {
        'complete': True, 'source_path': 'one-device-review.json',
        'source_sha256': hashlib.sha256(reviews['one-device-review.json'].encode()).hexdigest()}
    scene = expand(plan, no_device_base=base, one_device_base=one)[case_id]
    return {'diagnostic-scene.json': text(scene),
            'diagnostic-corridor.xodr': map_text,
            **{'diagnostic-' + name: value for name, value in reviews.items()}}


def stage_diagnostic(root):
    root = Path(root)
    names = {'diagnostic-scene.json': 'scene.json',
             'diagnostic-corridor.xodr': 'candidate-corridor.xodr',
             'diagnostic-no-device-review.json': 'no-device-review.json',
             'diagnostic-one-device-review.json': 'one-device-review.json',
             'diagnostic-camera-review.json': 'camera-review.json'}
    if any(not (root / source).is_file() for source in names):
        raise ValueError('selected offline diagnostic sources missing')
    for source, target in names.items():
        shutil.copyfile(root / source, root / target)
    return json.loads((root / 'scene.json').read_text())


def stage_original(root, config):
    root = Path(root).resolve()
    source_name = os.environ.get('C227824_REVIEWED_SOURCE_DIR')
    if not source_name:
        raise ValueError('reviewed original pedestrian source directory required')
    source = Path(source_name).resolve()
    private = next((parent for parent in root.parents if parent.name == '.runtime-work'), None)
    if private is None or not source.is_dir() or not source.is_relative_to(private):
        raise ValueError('reviewed original source must be under .runtime-work')
    variant = config.get('source_variant', 'primary')
    if variant not in ('primary', 'fallback1'):
        raise ValueError('unknown selected source variant')
    suffix = '' if variant == 'primary' else '-fallback1'
    base_files = [source / ('no-device-base' + suffix + '.json'),
                  source / ('one-device-base' + suffix + '.json')]
    if any(not file.is_file() or file.is_symlink() for file in base_files):
        raise ValueError('reviewed original pedestrian base pair missing')
    plan = json.loads((root / 'case-plan.json').read_text())
    scenes = expand(plan, no_device_base=json.loads(base_files[0].read_text()),
                    one_device_base=json.loads(base_files[1].read_text()))
    scene = scenes[config['selected_case_id']]
    if scene.get('diagnostic_fixture') is True:
        raise ValueError('diagnostic scene cannot enter original Native capture')
    if sha(source / 'candidate-corridor.xodr') != scene.get('map_source_sha256'):
        raise ValueError('reviewed original map source hash differs')
    verify_source_authority(scene, source)
    names = {'candidate-corridor.xodr'}
    for key in ('device_inventory_review', 'camera_placement_review'):
        names.add(scene[key]['source_path'])
    for key in ('official_signal', 'pedestrian_device_driver',
                'highway_boundary_survey'):
        names.add(scene['production_source_review'][key]['path'])
    for name in names:
        if (not isinstance(name, str) or not name or Path(name).name != name or
                (source / name).is_symlink()):
            raise ValueError('reviewed original source path invalid')
        shutil.copyfile(source / name, root / name)
    (root / 'scene.json').write_text(text(scene))
    verify_source_authority(scene, root)
    return scene
