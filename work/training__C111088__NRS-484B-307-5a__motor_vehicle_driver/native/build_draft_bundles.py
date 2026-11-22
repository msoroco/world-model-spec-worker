"""Rebuild source-bound exact C111088 draft constructions under work/."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cameras import camera_plan
from engineering import BASE, KNOBS, parameters

PACKAGE = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
SOURCES = ('runner.py', 'controller.py', 'geometry.py', 'engineering.py',
           'cameras.py', 'measure.py', 'finalize.py', 'road.xodr')
TESTS = ('test_controller.py', 'test_measure.py', 'test_finalizer.py')
TERMS = ('dev.traffic_signal', 'dev.governs', 'drv.turning', 'kin.heading',
         'drv.entering_intersection', 'st.crosswalk', 'drv.in_intersection',
         'drv.yields_to', 'st.intersection', 'kin.position',
         'native_body_pose_control', 'camera_frame_join')


def serialized(value):
    return json.dumps(value, indent=2, allow_nan=False, sort_keys=True) + '\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recording_description():
    return {'channels': [{
        'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
        'method': 'retained original Native signal, actor, body and frame map sources',
        'time_window': '42 s / 840 original joined frames',
        'reference_frame': 'surveyed Native map and original frame',
        'uncertainty': '50 ms sampling; displayed aspect and legal status need independent review'}
        for name in TERMS],
        'context_inputs': [{'name': 'surveyed_arrow_intersection', 'unit': 'structured',
                            'method': 'original Native OpenDRIVE and signal actor readback'}],
        'limitations': ['CPU diagnostic fixtures are not original CARLA observations']}


def build():
    assignment = json.loads((Path('inputs') / BASE / 'assignment.json').read_text())
    recording = recording_description()
    manifest = {
        'format': 'worker-selected-proof-manifest-v1',
        'assignment_id': BASE,
        'runtime_manifest_sha256': json.loads(Path('batch.json').read_text())['runtime']['source_manifest_sha256'],
        'status': 'draft_exact_offline_only', 'cases': []}
    for suffix in ('false', 'true'):
        case_id = BASE + '__' + suffix
        candidates = []
        primary = None
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = parameters(case_id, candidate)
            config = {
                **selected, 'cell_id': assignment['cell_id'],
                'law_id': assignment['law_id'], 'actor': assignment['actor'],
                'selected_case_id': case_id,
                'required_atoms': ['st.intersection', 'kin.position'],
                'source_packets': [],
                'cameras': [{key: spec[key] for key in ('name', 'width', 'height')}
                            for spec in camera_plan(candidate)],
                'case': {'case_id': case_id,
                         'comparison_variable': 'lawful_conflict_participant_present',
                         'requested_setting': suffix == 'true',
                         'recording_description': recording},
                'recording_description': recording,
            }
            files = [{'path': name, 'content': (NATIVE / name).read_text()}
                     for name in SOURCES]
            files.extend({'path': 'tests/' + name, 'content': (NATIVE / name).read_text()}
                         for name in TESTS)
            files.append({'path': 'config.json', 'content': serialized(config)})
            construction = {
                'case_id': case_id, 'cell_id': assignment['cell_id'],
                'law_id': assignment['law_id'], 'actor': assignment['actor'],
                'entrypoint': 'runner.py', 'files': files,
                'recording_description': recording,
                'measurement_plan': {
                    'method': 'saved original sole-arrow pixel review, prior green entry, other vehicle occupancy and ego stop-line crossing',
                    'status': 'draft_unproven'},
                'static_checks': ['42-second Native and four-source-camera frame joins',
                                  'same-frame signal/actor yield action',
                                  'source-bound saved measurement and no-turn check'],
                'termination_rules': ['840 original joined frames', 'restore owned Native world'],
                'mechanisms': ['prior west green entry', 'sole south straight arrow',
                               'ego straight hold and release'],
                'status': 'draft_cpu_offline_proof_pending'}
            relative = Path('draft-candidates') / suffix / candidate / 'construction.json'
            path = PACKAGE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized(construction))
            entry = {'id': candidate, 'construction': str(relative),
                     'construction_sha256': digest(path)}
            if candidate == 'primary':
                primary = entry
            else:
                trigger = {
                    'fallback1': ('other_vehicle_conflict_clearance_s',
                                  'insufficient observed clearance before ego entry'),
                    'fallback2': ('ego_stop_line_overshoot_m',
                                  'ego front passes stop line before other vehicle clears'),
                    'fallback3': ('signal_head_visibility_fraction',
                                  'sole straight-arrow head not readable in original pixels')
                }[candidate]
                entry.update({
                    'trigger': {'metric': trigger[0], 'source': 'original Native actor/body and source-camera review',
                                'failure_condition': trigger[1]},
                    'changed_knobs': [key for key, value in KNOBS[candidate].items()
                                      if value != KNOBS['primary'][key]]})
                candidates.append(entry)
        manifest['cases'].append({
            'case_id': case_id, 'kind': 'delivery',
            'candidate_risk': {'status': 'physical',
                               'reason': 'Native signal aspect, conflict timing and source pixels require local physical review'},
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c111088-saved-source-analysis-v1'},
            'id': primary['id'], 'construction': primary['construction'],
            'construction_sha256': primary['construction_sha256'],
            'candidates': candidates})
    target = PACKAGE / 'draft-proof-manifest.json'
    target.write_text(serialized(manifest))
    return {'manifest': str(target), 'cases': len(manifest['cases']),
            'candidate_constructions': sum(1 + len(e['candidates']) for e in manifest['cases'])}


if __name__ == '__main__':
    print(serialized(build()), end='')
