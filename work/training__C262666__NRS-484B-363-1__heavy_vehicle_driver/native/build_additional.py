"""Materialize seven exact school-zone comparison bundles without CARLA."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C262666__NRS-484B-363-1__heavy_vehicle_driver'
SPECS = {
    'probe_01': (14, 'active designated zone below 15 mph'),
    'probe_02': (15, 'active designated zone at the exact 15 mph boundary'),
    'probe_04': (17, 'above 15 mph on a day when school is not in session'),
    'probe_05': (17, 'above 15 mph during the half-hour after school ceases or before it resumes'),
    'probe_06': (17, 'above 15 mph during class hours with an operational beacon not flashing'),
    'probe_07': (17, 'above 15 mph with no operational beacon and a sign indicating the limit is in effect'),
    'probe_08': (17, 'above 15 mph with no operational beacon and a sign indicating the limit is not in effect'),
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n')


def generate():
    primary = HERE/'selected_primary'
    runner_template = (primary/'runner.py').read_text()
    marker = "CASE = AID + '__probe_03'"
    if runner_template.count(marker) != 1:
        raise ValueError('Exact primary case marker changed')
    tests = (primary/'tests/test_bundle.py').read_text()
    config_template = json.loads((primary/'config.json').read_text())
    entries = []
    for suffix, (mph, context) in SPECS.items():
        case_id = AID+'__'+suffix
        bundle = HERE/'cases'/suffix
        runner = runner_template.replace(marker, "CASE = AID + '__"+suffix+"'")
        config = dict(config_template)
        config.update(case_id=case_id, selected_case_id=case_id,
                      target_mph=mph, planned_context=context)
        config['case'] = {'case_id': case_id,
                          'recording_description': config['recording_description']}
        (bundle/'tests').mkdir(parents=True, exist_ok=True)
        (bundle/'runner.py').write_text(runner)
        write(bundle/'config.json', config)
        (bundle/'tests/test_bundle.py').write_text(tests)
        files = [{'path': name, 'content': (bundle/name).read_text()}
                 for name in ('runner.py', 'config.json', 'tests/test_bundle.py')]
        files.append({'path': 'finalize.py', 'content': (primary/'finalize.py').read_text()})
        files.append({'path': 'measure_school_zone.py',
                      'content': (HERE/'measure_school_zone.py').read_text()})
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case_id, 'cell_id': 'C262666',
                        'law_id': 'NRS-484B-363-1', 'actor': 'heavy_vehicle_driver',
                        'entrypoint': 'runner.py',
                        'recording_description': config['recording_description'],
                        'files': files}
        path = bundle/'construction.json'
        write(path, construction)
        entries.append({'case_id': case_id,
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Local heavy-vehicle route and reviewed school-zone sign/beacon visibility may require an engineering fallback'},
                        'candidates': []})
    manifest = {'assignment_id': AID, 'cases': entries}
    write(HERE/'additional-offline-manifest.json', manifest)
    return {'generated_cases': [e['case_id'] for e in entries], 'case_count': len(entries)}


if __name__ == '__main__':
    print(json.dumps(generate(), sort_keys=True))
