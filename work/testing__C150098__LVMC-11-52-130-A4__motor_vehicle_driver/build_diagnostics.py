"""Create case-specific synthetic source fixtures for compatibility only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from hydrant import ASSIGNMENT, CASES, target_interval

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
    site = {'assignment_id': ASSIGNMENT, 'cell_id': 'C150098',
            'layout': 'one_way_road', 'control': 'fire_hydrant',
            'parallel_parking_permitted': True, 'hydrant_physical_support': 'spawned_prop',
            'hydrant': {'west_x_m': 0.0, 'east_x_m': .5,
                        'curb_y_m': -2.0, 'depth_m': .4},
            'approach_waypoints': [[-20, -2], [20, -2]],
            'property_status': 'private', 'sign_status': 'absent',
            'red_paint_status': 'absent'}
    for key in ('map', 'municipal_jurisdiction', 'parallel_parking_authority',
                'hydrant_identity', 'hydrant_geometry', 'hydrant_blueprint',
                'curb_source', 'one_way_direction', 'ego_blueprint', 'camera_plan'):
        site[key + '_sha256'] = hashlib.sha256(('synthetic-diagnostic-' + key).encode()).hexdigest()
    if case.exception != 'none':
        key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
               'police_direction': 'police_direction_source_sha256',
               'traffic_device_direction': 'traffic_device_source_sha256'}[case.exception]
        site[key] = hashlib.sha256(('synthetic-diagnostic-' + key).encode()).hexdigest()
    return site


def build():
    SHARED.mkdir(parents=True, exist_ok=True)
    for relative in SOURCE_FILES:
        source = DONOR_CASE / relative
        target = SHARED / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha(target) != sha(source):
            shutil.copyfile(source, target)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('shared diagnostic source exceeds 2 MiB')
    base = json.loads(DONOR_GENERATOR.read_text(encoding='utf-8'))
    branch = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))['selected_branches'][0]
    for case in CASES:
        name = case.suffix
        case_id = ASSIGNMENT + '__' + name
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        site = site_for(case)
        site_path = folder / 'site.json'
        write(site_path, site)
        site_sha = sha(site_path)
        note_path = folder / 'diagnostic-source-note.json'
        write(note_path, {'case_id': case_id,
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False,
            'scope': 'Software finalizer, Core and video decode only; no municipal or physical evidence.'})
        camera_rows = [dict(frame_index=i, native_frame=100 + i,
            time_s=i / 20, camera_frames={view: 100 + i for view in CAMERAS})
                       for i in range(900)]
        camera_path = folder / 'camera-frame-map.jsonl'
        camera_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                       for row in camera_rows), encoding='utf-8')
        g = copy.deepcopy(base)
        capture_manifest = json.loads(g['files']['capture/manifest.json'])
        capture_manifest['case_id'] = case_id
        g['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (name + '-generator.json')
        write(generator_path, g, compact=True)
        west, east = target_interval(site, case, 4.0)
        fixed = {'actor_id': 10, 'hydrant_actor_id': 22,
                 'map_sha256': site['map_sha256'], 'site_sha256': site_sha,
                 'hydrant_identity_sha256': site['hydrant_identity_sha256'],
                 'hydrant_geometry_sha256': site['hydrant_geometry_sha256'],
                 'parallel_parking_authority_sha256': site['parallel_parking_authority_sha256'],
                 'camera_plan_sha256': site['camera_plan_sha256']}
        activity = {'stop': 'stopped', 'stand': 'standing', 'park': 'parked'}[case.activity]
        history = [dict(fixed, case_id=case_id, frame=100 + i, time_s=i / 20,
            hydrant_physically_present=True, body_source_sha256=sha(generator_path),
            frame_map_sha256=sha(camera_path), body_west_x_m=west,
            body_east_x_m=east, activity_observation=activity,
            exception_kind=case.exception,
            exception_source_sha256=site.get({
                'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                'police_direction': 'police_direction_source_sha256',
                'traffic_device_direction': 'traffic_device_source_sha256'}.get(case.exception, ''), None))
            for i in range(900)]
        history_path = folder / 'original-hydrant-history.jsonl'
        history_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                        for row in history), encoding='utf-8')
        if history_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('case history exceeds 2 MiB')
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                'requirement': branch['requirement'], 'source': branch['source'],
                'output_key': 'hydrant_parallel_distance',
                'method': 'measure_hydrant_distance', 'value_type': 'object',
                'kind': 'measured',
                'inputs': ['site.json', 'original-hydrant-history.jsonl',
                           'diagnostic-source-note.json']}],
            'negative': {'remove': ['original-hydrant-history.jsonl'],
                'error_contains': 'Missing required source: original-hydrant-history.jsonl'}}
        write(HERE / 'diagnostics' / (name + '-measurement-contract.json'), contract)
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({'path': relative,
                'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        for relative in ('site.json', 'diagnostic-source-note.json',
                         'camera-frame-map.jsonl', 'original-hydrant-history.jsonl'):
            source = folder / relative
            sources.append({'path': relative,
                'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        write(HERE / 'diagnostics' / (name + '-recipe.json'), {
            'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': str(generator_path.relative_to(ROOT)),
                          'sha256': sha(generator_path)}})


if __name__ == '__main__':
    build()
