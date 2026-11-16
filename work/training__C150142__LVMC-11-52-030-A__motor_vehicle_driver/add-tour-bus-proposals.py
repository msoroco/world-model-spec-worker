"""Add the four authored tour-bus diagnostic case definitions without changing prior cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals/cases.json'
SUFFIXES = ('tour_bus_below', 'tour_bus_at', 'tour_bus_above', 'tour_bus_no_loading')


def build():
    document = json.loads(PROPOSALS.read_text())
    matrix = {case['case_id']: case for case in json.loads(
        (ROOT / 'exception-case-matrix.json').read_text())['cases']}
    old = {case['case_id']: case for case in document['cases']}
    for suffix in SUFFIXES:
        case_id = ROOT.name + '__' + suffix
        plan = matrix[case_id]
        construction = json.loads((ROOT / 'selected-primary' / suffix /
                                   'construction.json').read_text())
        assert plan['service_class'] == 'tour_bus'
        assert construction['case_id'] == case_id
        duration = plan['requested_stationary_duration_s']
        loading = plan['activity_request'] == 'passenger_loading'
        case = {
            'case_id': case_id,
            'target_law_id': 'LVMC-11-52-030-A',
            'target_type': 'attempt',
            'rationale': ('Tour-bus red-curb signed exception probe: retained source '
                          'must establish service class, applicable sign, stopped '
                          'interval, and passenger activity. This construction '
                          'requests ' + str(duration) + ' s and ' +
                          ('loading' if loading else 'no loading') +
                          '; no legal or physical outcome is assigned.'),
            'variable_assignments': {
                'road_and_actors': {'kind': 'world_setup',
                    'value': 'authored red curb, tour/shuttle/limo sign, tour-bus ego' +
                    (', passenger walker' if loading else ', no passenger walker')},
                'service_class': {'kind': 'world_setup', 'value': 'tour_bus'},
                'sign_classes': {'kind': 'world_setup', 'value': plan['sign_classes']},
                'requested_parking_x_m': {'kind': 'controller', 'value': 40, 'unit': 'm'},
                'requested_stationary_duration_s': {'kind': 'controller',
                    'value': duration, 'unit': 's'},
                'passenger_loading_request': {'kind': 'controller',
                    'value': loading},
                'red_curb_stop_or_park': {'kind': 'subject_behavior', 'value': None},
            },
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [
                'Actual sign applicability, passenger purpose, stopped duration, '
                'red curb occupancy and legal exception require independent review.'
            ],
        }
        if case_id in old:
            assert old[case_id] == case, 'Existing proposal differs: ' + case_id
        else:
            document['cases'].append(case)
    PROPOSALS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return [ROOT.name + '__' + suffix for suffix in SUFFIXES]


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
