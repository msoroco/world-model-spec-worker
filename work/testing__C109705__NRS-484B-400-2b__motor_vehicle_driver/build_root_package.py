"""Build the portable top-level return artifact from reviewed case sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ('runner.py', 'construction.py', 'analysis.py',
           'native_map.py', 'native_capture.py', 'native_camera_source.py',
           'native_ego_adapter.py', 'native_seal.py', 'native_publication.py',
           'departure_geometry.py',
           'saved_delivery.py', 'saved_pixels.py', 'finalize.py',
           'comparison_audit.py')


def build():
    plan_bytes = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    cases = [item['case_id'] for item in plan['cases']]
    primary = json.loads((HERE / 'construction-near_centerline.json').read_text())
    selected_config = json.loads(next(f['content'] for f in primary['files']
                                      if f['path'] == 'config.json'))
    config = {
        'assignment_id': HERE.name, 'law_id': plan['law_id'],
        'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'selected_case_id': cases[0], 'supported_case_ids': cases,
        'rate_hz': 20, 'duration_s': 45,
        'cameras': [
            {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 90,
             'pose_strategy': 'elevated complete intersection and destination view'},
            {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 90,
             'pose_strategy': 'approach and entry view with complete ego body'},
            {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 90,
             'pose_strategy': 'destination centerline and full-body departure view'},
            {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
             'pose_strategy': 'driver forward view through connected left turn'},
        ],
        'required_atoms': [], 'source_packets': [],
        'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
        'native_map_survey': 'required_before_capture',
        'legal_lateral_cutoff': None,
        'case': {'case_id': cases[0],
                 'recording_description': primary['recording_description']},
        'departure_centerline_kind': selected_config['departure_centerline_kind'],
        'departure_position_target': selected_config['departure_position_target'],
    }
    config_text = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
    (HERE / 'config.json').write_text(config_text)
    description = {'channels': [
        {'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
         'method': method, 'time_window': 'complete sampled original episode',
         'reference_frame': 'Native map and CARLA tick',
         'uncertainty': 'original source sampling and review pending'}
        for name, method in (
            ('activation_and_context', 'source-sealed control, intersection and highway review'),
            ('destination_centerline', 'reviewed mapped or source-derived imaginary line'),
            ('full_body_departure_position', 'original full-body corner projection after entry'),
            ('video_visibility', 'four original camera streams and frame join'))],
        'context_inputs': [],
        'limitations': ['Diagnostic fixtures do not prove original Native physical completion or a statutory judgment.']}
    files = [{'path': name, 'content': (HERE / name).read_text(),
              'source': 'work/' + HERE.name + '/' + name} for name in SOURCES]
    files.append({'path': 'config.json', 'content': config_text})
    construction = {
        'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'case_id': cases[0], 'entrypoint': 'runner.py', 'files': files,
        'recording_description': description,
        'measurement_plan': [
            'source-sealed driver control, two-directional highway status and intersection entry',
            'mapped or reviewed source-derived destination centerline',
            'per-frame full-body signed right-side extrema after entry',
            'all four original camera streams and frame/time joins'],
        'static_checks': ['exact law/cell/case identity', '20 Hz and 45 s capture profile',
                          'source-hashed original map, trace and cameras'],
        'source_kind': 'source-reviewed Native acquisition required',
        'termination_rules': ['stop on lost source frame or map identity',
                              'stop on completed 900-frame original episode'],
        'mechanisms': ['synchronous CARLA capture', 'saved-only source-bound finalization',
                       'diagnostic compatibility is separate from physical acceptance'],
    }
    (HERE / 'construction.json').write_text(json.dumps(construction, indent=2,
                                                       ensure_ascii=False) + '\n')
    print('built top-level four-case return artifact')


if __name__ == '__main__':
    build()
