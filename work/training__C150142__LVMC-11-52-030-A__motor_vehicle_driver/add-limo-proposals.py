"""Append provisional limousine exception proposals without altering prior cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals/cases.json'


def build():
    document = json.loads(PROPOSALS.read_text())
    matrix = {row['case_id']: row for row in json.loads(
        (ROOT / 'exception-case-matrix.json').read_text())['cases']}
    existing = {row['case_id']: row for row in document['cases']}
    added = []
    for boundary in ('below', 'at', 'above', 'no_loading'):
        case = 'limo_' + boundary
        case_id = ROOT.name + '__' + case
        plan = matrix[case_id]
        construction = json.loads((ROOT / 'selected-primary' / case /
                                   'construction.json').read_text())
        if plan['service_class'] != 'limo' or construction['case_id'] != case_id:
            raise ValueError('Limo proposal source differs: ' + case)
        duration = plan['requested_stationary_duration_s']
        loading = plan['activity_request'] == 'passenger_loading'
        proposal = {
            'case_id': case_id, 'target_law_id': 'LVMC-11-52-030-A',
            'target_type': 'attempt',
            'rationale': ('Provisional limousine-service signed red-curb probe. '
                          'Retained Native sources must establish sign, stopped '
                          'interval and passenger activity. The Lincoln MKZ '
                          'sedan does not establish a limousine body, licensing '
                          'or qualifying service. This construction requests '
                          f'{duration} s and ' +
                          ('loading' if loading else 'no loading') +
                          '; no legal or physical outcome is assigned.'),
            'variable_assignments': {
                'road_and_actors': {'kind': 'world_setup',
                    'value': ('authored red curb and tour/shuttle/limo sign; '
                              'Lincoln MKZ sedan with provisional limo service plan' +
                              (', passenger walker' if loading else
                               ', no passenger walker'))},
                'service_class': {'kind': 'world_setup', 'value': 'limo'},
                'sign_classes': {'kind': 'world_setup', 'value': plan['sign_classes']},
                'requested_parking_x_m': {'kind': 'controller', 'value': 40, 'unit': 'm'},
                'requested_stationary_duration_s': {'kind': 'controller',
                                                    'value': duration, 'unit': 's'},
                'passenger_loading_request': {'kind': 'controller', 'value': loading},
                'red_curb_stop_or_park': {'kind': 'subject_behavior', 'value': None}},
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [
                'Actual limousine service identity, body and licensing, sign '
                'applicability, passenger purpose, stopped duration, red curb '
                'occupancy and legal exception require independent review.'],
        }
        if case_id in existing:
            if existing[case_id] != proposal:
                raise ValueError('Existing limo proposal differs: ' + case_id)
        else:
            document['cases'].append(proposal)
            added.append(case_id)
    PROPOSALS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return added


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
