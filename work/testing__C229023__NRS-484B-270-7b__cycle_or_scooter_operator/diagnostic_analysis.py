"""Synthetic source-shaped software fixture; never an original pass measurement."""

import hashlib
import json
from pathlib import Path

from overtake import require


def required(root, name):
    target = Path(root) / name
    require(target.is_file() and not target.is_symlink(),
            'Missing required source: ' + name)
    return target


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    marker = json.loads(required(root, 'diagnostic-source-note.json').read_text())
    require(marker.get('source_kind') == 'synthetic_diagnostic_fixture' and
            marker.get('accepted_original_source') is False,
            'synthetic diagnostic provenance missing')
    source = required(root, 'pass-rows.json')
    rows = json.loads(source.read_text())
    require(len(rows) == 900, '900 synthetic joined pass rows required')
    case = config['case']
    for i, row in enumerate(rows):
        require(row.get('frame') == i and
                abs(row.get('time_s', -1) - i / 20) < 1e-8 and
                row.get('cycle_kind') == case['cycle_kind'] and
                row.get('pass_policy') == case['pass_policy'],
                'synthetic frame/cycle/pass join differs')
    require(rows[0]['relative_station_m'] < 0 and
            any(abs(row['relative_station_m']) <= 1 for row in rows),
            'synthetic behind/alongside phase absent')
    terminal = rows[-1]['relative_station_m']
    require((terminal > 0) == (case['pass_policy'] == 'complete'),
            'synthetic pass completion differs')
    observation = {'case_id': case['case_id'], 'frame_count': len(rows),
                   'cycle_kind': case['cycle_kind'],
                   'pass_policy': case['pass_policy'],
                   'requested_lateral_offset_m': case['lateral_offset_request_m'],
                   'initial_relative_station_m': rows[0]['relative_station_m'],
                   'terminal_relative_station_m': terminal,
                   'minimum_surface_clearance_m': min(row['surface_clearance_m']
                                                      for row in rows),
                   'maximum_closing_speed_mps': max(row['closing_speed_mps']
                                                    for row in rows),
                   'safe_pass_judgment': None,
                   'endangerment_judgment': None,
                   'legal_judgment': None}
    sources = {'pass-rows.json': sha(source),
               'diagnostic-source-note.json': sha(required(root,
                                                          'diagnostic-source-note.json'))}
    channel_values = {
        'relative_station': lambda row: row['relative_station_m'],
        'surface_clearance': lambda row: row['surface_clearance_m'],
        'closing_speed': lambda row: row['closing_speed_mps'],
        'camera_frame_identity': lambda row: row['frame']}
    evidence = []
    for channel in case['recording_description']['channels']:
        name = channel['name']
        require(name in channel_values, 'unknown diagnostic channel')
        dest = root / ('channel-' + name + '.jsonl')
        dest.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': channel_values[name](row)}) + '\n'
                                for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': dest.name})
    from worker_exchange.native_output import physical_result, write_result
    native = {'case_id': case['case_id'], 'measured_values': observation,
              'target_checks': [{'target': 'synthetic cycle/motor pass protocol',
                                 'requested': case, 'measured': observation,
                                 'method': '900 synthetic joined rows',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_cycle_motor_scene_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner',
                                    'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': case['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': True,
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    write_result(root, physical_result(root, native))
    return {'format': 'worker-analysis-report', 'case_id': case['case_id'],
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'measurements': {'cycle_motor_pass': {'method': 'measure_case',
                                                  'value': observation,
                                                  'sources': sources}},
            'limitations': ['Synthetic fixture tests software only; original motion, occupant exposure and legal safety remain open.']}
