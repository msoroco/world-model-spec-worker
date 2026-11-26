"""Create case-specific synthetic truck sources for software compatibility only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from truck_following import CASES
from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONOR = ROOT / 'work/testing__C24751__NRS-484B-310-1__heavy_vehicle_driver/diagnostics'
DONOR_CASE = DONOR / '_shared'
DONOR_GENERATOR = DONOR / 'crosswalk_stop-generator.json'
SHARED = HERE / 'diagnostics/_shared'
SOURCE_FILES = ('trace.jsonl', 'video_frames.jsonl',
                'capture/native/frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n', encoding='utf-8')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic source exceeds 2 MiB: ' + str(path))


def frame(index, case, case_id):
    gap = case.gap_target_m
    subject_start = 0.0
    phase = 'following'
    lane_relation = 'follow_lane'
    if case.passing:
        if index >= 700:
            subject_start, phase, lane_relation = 300.0, 'returned', 'follow_lane'
        elif index >= 600:
            subject_start, phase, lane_relation = 300.0, 'ahead', 'opposing_lane'
        elif index >= 500:
            phase, lane_relation = 'opposing', 'opposing_lane'
    subject = {'identity': 'subject', 'vehicle_class': 'truck',
               'route_vertex_s_m': [subject_start + j for j in range(8)],
               'overall_width_m': case.ego_width_target_m, 'mesh_width_verified': True}
    lead_start = 7 + gap
    lead = {'identity': 'lead', 'vehicle_class': 'truck',
            'route_vertex_s_m': [lead_start + j for j in range(8)],
            'overall_width_m': case.lead_width_target_m, 'mesh_width_verified': True}
    bodies = [subject, lead]
    if case.circumstance == 'constrained':
        bodies.append({'identity': 'surrounding-car', 'vehicle_class': 'car',
                       'route_vertex_s_m': [250 + j for j in range(8)]})
    if case.entering_vehicle and index == 480:
        bodies.append({'identity': 'passing-car', 'vehicle_class': 'car',
                       'route_vertex_s_m': [20 + j for j in range(8)]})
    lanes = [{'lane_id': 'same-' + str(j), 'direction_dot': 1.0,
              'available': True, 'connected': True}
             for j in range(case.available_same_direction_lanes)]
    lanes.append({'lane_id': 'opposing', 'direction_dot': -1.0,
                  'available': True, 'connected': True})
    return {'case_id': case_id, 'frame': index, 'native_frame': 100 + index,
            'time_s': index / 20, 'bodies': bodies,
            'lane_source': {'source_kind': 'native_map_readback', 'highway_public': True,
                            'available_same_direction_lanes': case.available_same_direction_lanes,
                            'driving_lanes': lanes},
            'pass_phase': phase, 'subject_lane_relation': lane_relation,
            'controller_commands': []}


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
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    for case in CASES:
        name, case_id = case.suffix, AID + '__' + case.suffix
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        note_path = folder / 'diagnostic-source-note.json'
        write(note_path, {'case_id': case_id,
                          'source_kind': 'synthetic_diagnostic_fixture',
                          'accepted_original_source': False,
                          'scope': 'Software finalizer, Core and decode only; no actual truck motion evidence.'})
        camera_rows = [dict(frame_index=i, native_frame=100 + i,
                            time_s=i / 20,
                            camera_frames={view: 100 + i for view in VIEWS})
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
        history_path = folder / 'original-truck-history.jsonl'
        history_path.write_text(''.join(json.dumps(frame(i, case, case_id), separators=(',', ':')) + '\n'
                                        for i in range(900)), encoding='utf-8')
        if history_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('case history exceeds 2 MiB')
        relevant = [row for row in plan['requirement_dispositions']
                    if case_id in row['case_ids']]
        write(HERE / 'diagnostics' / (name + '-measurement-contract.json'), {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': row['disposition_index'],
                'requirement': row['requirement'], 'source': row['source'],
                'output_key': 'truck_requirement_' + str(row['disposition_index']),
                'method': 'audit_original_frames', 'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-truck-history.jsonl', 'diagnostic-source-note.json']}
                for row in relevant],
            'negative': {'remove': ['original-truck-history.jsonl'],
                'error_contains': 'Missing required source: original-truck-history.jsonl'}})
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({'path': relative,
                            'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        for relative in ('diagnostic-source-note.json',
                         'camera-frame-map.jsonl', 'original-truck-history.jsonl'):
            source = folder / relative
            sources.append({'path': relative,
                            'source': str(source.relative_to(ROOT)), 'sha256': sha(source)})
        write(HERE / 'diagnostics' / (name + '-recipe.json'), {
            'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': str(generator_path.relative_to(ROOT)),
                          'sha256': sha(generator_path)}})


if __name__ == '__main__':
    build()
