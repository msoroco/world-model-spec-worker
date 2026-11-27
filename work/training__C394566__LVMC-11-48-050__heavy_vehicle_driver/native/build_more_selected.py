"""Extend the exact Native manifest with the remaining statutory contrasts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
NATIVE = FOLDER / 'native'
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    manifest_path = FOLDER / 'execution-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [entry for entry in manifest['cases']
                         if entry['case_id'].endswith(('__truck_route', '__non_truck_route'))]
    base = json.loads((NATIVE / 'config.json').read_text())
    standard = {name: (NATIVE / name).read_text() for name in
                ('runner.py', 'source_contract.py', 'route_measurement.py')}
    standard['restriction_measure.py'] = (FOLDER / 'restriction_measure.py').read_text()
    test = json.loads((NATIVE / 'truck_route/primary/construction.json').read_text())
    test = next(item['content'] for item in test['files'] if item['path'] == 'tests/test_bundle.py')
    all_ids = [case['case_id'] for case in plan['cases']]
    for case_plan in plan['cases']:
        case = case_plan['case_id']
        suffix = case.removeprefix(AID + '__')
        if suffix in ('truck_route', 'non_truck_route'):
            continue
        permit = suffix.startswith('permit_')
        stationary = suffix == 'stationary'
        fixed = dict(standard)
        fixed['finalize.py'] = (NATIVE / ('finalize_permit.py' if permit else 'finalize.py')).read_text()
        risk = {'status': 'none' if stationary else 'physical',
                'reason': ('Stationary hold uses full brake and no planned route traversal.' if stationary else
                           'Surveyed original route may fail to reach the intended segment within 600 frames.')}
        entry = {'case_id': case, 'kind': 'delivery', 'candidate_risk': risk,
                 'measurement_contract': 'measurement-' + suffix + '.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'worker-analysis-report'},
                 'fixture_recipe': 'work/' + AID + '/fixture-recipe-' + suffix + '.json',
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                 'candidates': []}
        candidates = [('primary', 0.0 if stationary else 5.0)]
        if not stationary:
            candidates.append(('fallback1', 3.5))
        for candidate, speed in candidates:
            cfg = dict(base)
            cfg.update(case_id=case, selected_case_id=case, candidate_id=candidate,
                       target_speed_mps=speed, requested_motion='stationary' if stationary else 'moving',
                       requested_truck_route=False,
                       case={'case_id': case, 'requested_setting': suffix},
                       supported_case_ids=all_ids)
            files = [{'path': name, 'content': content} for name, content in fixed.items()]
            files += [{'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'},
                      {'path': 'tests/test_bundle.py', 'content': test}]
            construction = {'format': 'worker-construction', 'assignment_id': AID,
                            'case_id': case, 'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                            'actor': plan['actor'], 'entrypoint': 'runner.py',
                            'recording_description': cfg['recording_description'],
                            'files': files,
                            'measurement_plan': {'source': 'sealed original Native plus cited factual authority',
                                                 'expected_frames': 600, 'legal_verdict': None},
                            'static_checks': ['identity', 'four camera profile', 'original-source requirement'],
                            'termination_rules': ['600 joined original frames or explicit failure'],
                            'mechanisms': ['surveyed heavy vehicle route', 'source-joined factual context']}
            path = NATIVE / suffix / candidate / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2) + '\n')
            relative = str(path.relative_to(FOLDER))
            digest = sha(path)
            if candidate == 'primary':
                entry.update(construction=relative, construction_sha256=digest)
            else:
                entry['candidates'].append({'id': candidate, 'construction': relative,
                    'construction_sha256': digest,
                    'trigger': {'source': 'original Native road/pose trace',
                                'metric': 'distance and arrival at surveyed road target within 600 frames',
                                'failure_condition': 'primary overshoots or fails to reach surveyed target with joined original frames'},
                    'changed_knobs': ['target_speed_mps: 5.0 -> 3.5']})
        manifest['cases'].append(entry)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']),
                      'candidates': sum(1 + len(entry['candidates']) for entry in manifest['cases'])}))


if __name__ == '__main__':
    build()
