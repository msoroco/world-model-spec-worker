"""Bind both through-route cases to exact inline Native constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C394566__LVMC-11-48-060__motor_vehicle_driver'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    cases = []
    for probe, bundle_name, stem in (
            ('probe_01', 'selected_primary', 'selected-primary'),
            ('probe_02', 'selected_purpose', 'selected-purpose')):
        case_id = AID + '__' + probe
        names = ('runner.py', 'config.json', 'tests/test_bundle.py',
                 'finalize.py', 'measure_through_route.py', 'measure_purpose_route.py')
        bindings = {}
        for candidate_id, source_name, suffix in (
                ('primary', bundle_name, ''),
                ('fallback1', bundle_name+'_fallback1', '-fallback1')):
            bundle = HERE/source_name
            files = [{'path': name, 'content': (bundle/name).read_text()} for name in names]
            construction = {'format': 'worker-construction', 'assignment_id': AID,
                            'case_id': case_id, 'cell_id': 'C394566', 'law_id': 'LVMC-11-48-060',
                            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                            'recording_description': json.loads((bundle/'config.json').read_text())['recording_description'],
                            'files': files}
            path = HERE/(stem+suffix+'-construction.json')
            write(path, construction)
            bindings[candidate_id] = {'construction': path.name,
                                      'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        cases.append({'case_id': case_id, 'construction': path.name,
                      'construction_sha256': bindings['primary']['construction_sha256'],
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Surveyed two-truck-route journey may exceed the 30-second capture or lack a safe service stop'},
                      'candidates': [dict({'id': 'fallback1',
                                           'trigger': {'source': 'original Native route trace',
                                                       'metric': 'complete three-road passage within 600 frames',
                                                       'failure_condition': 'primary trace does not reach exit truck route'},
                                           'changed_knobs': ['cruise speed target 6.0 to 7.5 m/s',
                                                             'throttle cap 0.7 to 0.8']},
                                          **bindings['fallback1'])]})
        cases[-1].update(bindings['primary'])
    manifest = {'assignment_id': AID, 'cases': cases}
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'cases': cases}, sort_keys=True))


if __name__ == '__main__':
    main()
