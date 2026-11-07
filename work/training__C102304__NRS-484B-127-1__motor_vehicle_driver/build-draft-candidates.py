"""Materialize eight exact unselected C102304 construction bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime'/'pipeline'))
from scenario_pipeline.worker_exchange.preparation import runtime_for
NATIVE = HERE/'native'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SOURCES = {'runner.py': 'runner.py', 'geometry.py': 'geometry.py',
           'engineering.py': 'engineering.py', 'measure_following.py': 'measure_following.py',
           'finalize.py': 'finalize.py', 'tests/test_engineering.py': 'test_engineering.py'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recording():
    methods = {
        'kin.speed': ('m/s', 'Original Native actor velocity for ego and moving lead'),
        'st.lane': ('structured', 'Original Native road/lane waypoint of both actors'),
        'rel.surface_gap': ('m', 'Original four-vertex body projection onto ego forward direction'),
        'rel.ahead_behind_in_lane': ('structured', 'Original body order and same-lane identities'),
        'native_body_pose_control': ('structured', 'Original body/pose/velocity and requested velocity'),
        'camera_frame_join': ('structured', 'Four source camera frames joined to Native frame/time')}
    return {'channels': [{'name': name, 'unit': unit, 'sampling_rate_hz': 20,
              'method': method, 'time_window': 'entire original 45 s / 900-frame attempt',
              'reference_frame': 'Native map, actor bodies and original frame',
              'uncertainty': 'Frame interval 50 ms; original pose/body and pixel validation required'}
              for name, (unit, method) in methods.items()],
            'context_inputs': [{'name': name, 'unit': 'structured',
              'method': 'Native map/weather/actor inventory and independent legal/pixel review'}
              for name in ('traffic','surface','visibility','highway_public_availability')],
            'limitations': ['Numeric gaps/headways are descriptive, never a reasonable/prudent cutoff',
                            'OpenDRIVE geometry does not prove public highway availability',
                            'Commanded velocities and camera mounts require physical and saved audit']}


def build():
    batch = json.loads((ROOT/'batch.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    runtime = runtime_for(ROOT, batch)
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': HERE.name, 'runtime_manifest_sha256': sha(runtime/'SOURCE-MANIFEST.json'),
        'status': 'draft_not_selected', 'cases': []}
    common = {name: (NATIVE/source).read_text() for name, source in SOURCES.items()}
    description = recording()
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        contract = HERE/'draft-following'/suffix/'measurement-contract.json'
        if json.loads(contract.read_text())['case_id'] != case_id:
            raise ValueError('Case measurement contract differs')
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'candidate_risk': {'status': 'physical',
                   'reason': 'Native spawn, hill tracking, gap control and original-pixel framing are unverified'},
                 'measurement_contract': str(contract.relative_to(HERE)),
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c102304-following-analysis-v1'},
                 'candidates': []}
        for candidate in NAMES:
            config = json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id, selected_case_id=case_id, case_suffix=suffix,
                          candidate_id=candidate, supported_case_ids=[case_id],
                          case={'case_id': case_id}, recording_description=description)
            files = [{'path': name, 'content': code} for name, code in common.items()]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'})
            construction = {'case_id': case_id, 'cell_id': 'C102304',
                'law_id': 'NRS-484B-127-1', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': files,
                'recording_description': description,
                'measurement_plan': {'method': 'Original Native body-based moving-follow interval',
                                     'status': 'prototype_not_runtime_compatible'},
                'static_checks': ['OpenDRIVE hill/lane geometry', 'four-view profile',
                                  'moving-lead measurement and bounded gap controller tests'],
                'termination_rules': ['900 original 20 Hz frames',
                                      'retain failed attempt on capture or restoration error'],
                'mechanisms': ['same-cell hill-crest following', 'moving apparatus lead',
                               'original body/velocity/road/lane samples',
                               'four synchronized lossless cameras'],
                'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{suffix}/{candidate}/construction.json'
            path = HERE/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2)+'\n')
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                trigger = {
                    'fallback1': ('original Native spawn body and surveyed crest location',
                        'spawn_to_crest_distance_m', 'distance < 85.0 m',
                        'ego spawn 15 m farther before crest'),
                    'fallback2': ('original Native body and route samples',
                        'maximum_gap_tracking_error_m', 'error > 2.0 m',
                        'gap-controller lookahead 8 m to 5 m'),
                    'fallback3': ('independent original-pixel lead-body visibility audit',
                        'lead_body_visible_fraction', 'fraction < 0.95',
                        'four camera FOVs 90 to 110 degrees and mounts 1.65 to 2.0 m')}
                source, metric, failure, changed = trigger[candidate]
                ref.update(trigger={'source': source, 'metric': metric,
                                    'failure_condition': failure},
                           changed_knobs=[changed])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    value = build()
    print(json.dumps({'cases': len(value['cases']),
                      'candidates': sum(1+len(c['candidates']) for c in value['cases']),
                      'status': value['status']}, sort_keys=True))
