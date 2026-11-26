"""Create four case-specific synthetic source fixtures for compatibility only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from flashing_red_native import ASSIGNMENT, CASES, reference

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONOR = ROOT / 'work/testing__C233829__LVMC-11-40-120__cycle_or_scooter_operator/diagnostics'
DONOR_CASE = DONOR / 'bicycle__path__usable_path'
DONOR_GENERATOR = DONOR / 'bicycle__path__usable_path-generator.json'
SHARED = HERE / 'diagnostics' / '_shared'
SOURCE_FILES = ('trace.jsonl', 'video_frames.jsonl',
                'capture/native/frames.jsonl', 'capture/evidence.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic source exceeds 2 MiB: ' + str(path))


def site_for(case):
    site = {'assignment_id': ASSIGNMENT, 'cell_id': 'C24751',
            'layout': 'blind_intersection', 'control': 'flashing_red_signal',
            'official_device': True, 'approach_id': 'eastbound',
            'signal_approach_id': 'eastbound', 'signal_support': 'spawned_prop',
            'occluder_support': 'spawned_prop', 'approach_waypoints': [[0, 0], [50, 0]],
            'lane_width_m': 3.8, 'ego_width_m': 2.5, 'ego_length_m': 10.0,
            'occluder_corners_m': [[10, 4], [12, 4], [12, 6], [10, 6]],
            'driver_eye_xy_m': [0, 0], 'cross_traffic_target_xy_m': [20, 10],
            'signal_geometry': {'x_m': 25.0, 'y_m': 0.0},
            'stop_references_m': {'crosswalk': 20.0 if case.reference == 'crosswalk' else None,
                                  'limit_line': 21.0 if case.reference == 'limit_line' else None,
                                  'intersection': 25.0}}
    for name in ('map', 'approach_source', 'signal_identity', 'signal_geometry',
                 'signal_blueprint', 'occluder_identity', 'occluder_geometry',
                 'occluder_blueprint', 'ego_blueprint', 'camera_plan', 'stop_geometry'):
        site[name + '_sha256'] = hashlib.sha256(('synthetic-diagnostic-' + name).encode()).hexdigest()
    return site


def build():
    SHARED.mkdir(parents=True, exist_ok=True)
    for relative in SOURCE_FILES:
        source, target = DONOR_CASE / relative, SHARED / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha(target) != sha(source):
            shutil.copyfile(source, target)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('shared diagnostic source exceeds 2 MiB')
    base = json.loads(DONOR_GENERATOR.read_text(encoding='utf-8'))
    branch = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))['selected_branches'][0]
    for case in CASES:
        name, case_id = case.suffix, ASSIGNMENT + '__' + case.suffix
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        site = site_for(case)
        site_path = folder / 'site.json'
        write(site_path, site)
        note_path = folder / 'diagnostic-source-note.json'
        write(note_path, {'case_id': case_id,
                          'source_kind': 'synthetic_diagnostic_fixture',
                          'accepted_original_source': False,
                          'scope': 'Software finalizer, Core and decode only; no actual signal or stop evidence.'})
        camera_rows = [dict(frame_index=i, native_frame=100 + i,
                            time_s=i / 20, camera_frames={view: 100 + i for view in CAMERAS})
                       for i in range(900)]
        camera_path = folder / 'camera-frame-map.jsonl'
        camera_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                       for row in camera_rows), encoding='utf-8')
        generator = copy.deepcopy(base)
        capture_manifest = json.loads(generator['files']['capture/manifest.json'])
        capture_manifest['case_id'] = case_id
        generator['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (name + '-generator.json')
        write(generator_path, generator, compact=True)
        fixed = {'actor_id': 10, 'signal_actor_id': 22, 'occluder_actor_id': 23,
                 'map_sha256': site['map_sha256'], 'site_sha256': sha(site_path),
                 'signal_identity_sha256': site['signal_identity_sha256'],
                 'occluder_identity_sha256': site['occluder_identity_sha256'],
                 'stop_geometry_sha256': site['stop_geometry_sha256'],
                 'camera_plan_sha256': site['camera_plan_sha256'],
                 'frame_map_sha256': sha(camera_path)}
        stop_x = reference(site, case) + case.stop_offset_m
        history = [dict(fixed, case_id=case_id, frame=100 + i, time_s=i / 20,
                        signal_approach_id='eastbound', official_device=True,
                        signal_physically_present=True, occluder_physically_present=True,
                        red_lit=(i % 4 < 2), front_m=stop_x,
                        speed_mps=0.0 if i >= 100 else 1.0)
                   for i in range(900)]
        history_path = folder / 'original-flashing-red-history.jsonl'
        history_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                        for row in history), encoding='utf-8')
        if history_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('case history exceeds 2 MiB')
        write(HERE / 'diagnostics' / (name + '-measurement-contract.json'), {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                'requirement': branch['requirement'], 'source': branch['source'],
                'output_key': 'flashing_red_heavy_vehicle_stop',
                'method': 'measure_original', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['site.json', 'original-flashing-red-history.jsonl',
                           'diagnostic-source-note.json']}],
            'negative': {'remove': ['original-flashing-red-history.jsonl'],
                'error_contains': 'Missing required source: original-flashing-red-history.jsonl'}})
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({'path': relative,
                            'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        for relative in ('site.json', 'diagnostic-source-note.json',
                         'camera-frame-map.jsonl', 'original-flashing-red-history.jsonl'):
            source = folder / relative
            sources.append({'path': relative,
                            'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        write(HERE / 'diagnostics' / (name + '-recipe.json'), {
            'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': str(generator_path.relative_to(ROOT)),
                          'sha256': sha(generator_path)}})


if __name__ == '__main__':
    build()
