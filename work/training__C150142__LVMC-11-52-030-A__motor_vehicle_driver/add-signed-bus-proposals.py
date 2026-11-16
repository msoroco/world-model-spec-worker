"""Add exact shuttle and RTC case proposals while preserving existing proposals."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals/cases.json'


def build():
    document = json.loads(PROPOSALS.read_text())
    matrix = {case['case_id']: case for case in json.loads(
        (ROOT / 'exception-case-matrix.json').read_text())['cases']}
    old = {case['case_id']: case for case in document['cases']}
    added = []
    for service, sign in (('shuttle_bus', 'tour/shuttle/limo'),
                          ('rtc_bus', 'RTC-only')):
        for boundary in ('below', 'at', 'above', 'no_loading'):
            suffix = service + '_' + boundary
            case_id = ROOT.name + '__' + suffix
            plan = matrix[case_id]
            construction = json.loads((ROOT / 'selected-primary' / suffix /
                                       'construction.json').read_text())
            if plan['service_class'] != service or construction['case_id'] != case_id:
                raise ValueError('Signed-bus proposal source differs: ' + suffix)
            duration = plan['requested_stationary_duration_s']
            loading = plan['activity_request'] == 'passenger_loading'
            case = {
                'case_id': case_id,
                'target_law_id': 'LVMC-11-52-030-A',
                'target_type': 'attempt',
                'rationale': (service.replace('_', ' ').title() +
                              ' red-curb signed exception probe: retained source '
                              'must establish the applicable sign, stopped interval '
                              'and passenger activity. Service identity remains '
                              'authored and unverified. This construction requests ' +
                              str(duration) + ' s and ' +
                              ('loading' if loading else 'no loading') +
                              '; no legal or physical outcome is assigned.'),
                'variable_assignments': {
                    'road_and_actors': {'kind': 'world_setup',
                        'value': ('authored red curb, ' + sign + ' sign, ' + service +
                                  ' ego on bus chassis' +
                                  (', passenger walker' if loading else
                                   ', no passenger walker'))},
                    'service_class': {'kind': 'world_setup', 'value': service},
                    'sign_classes': {'kind': 'world_setup',
                                     'value': plan['sign_classes']},
                    'requested_parking_x_m': {'kind': 'controller',
                                              'value': 40, 'unit': 'm'},
                    'requested_stationary_duration_s': {'kind': 'controller',
                                                        'value': duration, 'unit': 's'},
                    'passenger_loading_request': {'kind': 'controller',
                                                  'value': loading},
                    'red_curb_stop_or_park': {'kind': 'subject_behavior',
                                              'value': None},
                },
                'recording_description': construction['recording_description'],
                'unresolved_judgment_calls': [
                    'Actual service identity, sign applicability, passenger '
                    'purpose, stopped duration, red curb occupancy and legal '
                    'exception require independent review.'
                ],
            }
            if case_id in old:
                if old[case_id] != case:
                    raise ValueError('Existing proposal differs: ' + case_id)
            else:
                document['cases'].append(case)
                added.append(case_id)
    PROPOSALS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return added


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
