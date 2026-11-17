"""Add the exact unsigned emergency-business semantic proposal."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals/cases.json'
CASE = ROOT.name + '__emergency_vehicle_unsigned_business'


def build():
    document = json.loads(PROPOSALS.read_text())
    plan = next(row for row in json.loads(
        (ROOT / 'exception-case-matrix.json').read_text())['cases']
        if row['case_id'] == CASE)
    construction = json.loads((ROOT / 'selected-primary/emergency_vehicle_unsigned_business/construction.json').read_text())
    if (plan['service_class'], plan['sign_classes'], plan['activity_request'],
            plan['requested_stationary_duration_s']) != (
            'emergency_vehicle', [], 'business_activity', 12):
        raise ValueError('Emergency business source plan differs')
    proposal = {
        'case_id': CASE, 'target_law_id': 'LVMC-11-52-030-A',
        'target_type': 'attempt',
        'rationale': ('Unsigned red-curb emergency vehicle business probe. '
                      'Request a firetruck blueprint and a service worker '
                      'approach, dwell and departure during a 12-second stop. '
                      'Native identity, actual business purpose and whether '
                      'the stop was necessary remain unverified. No legal '
                      'or physical outcome is assigned.'),
        'variable_assignments': {
            'road_and_actors': {'kind': 'world_setup',
                'value': 'authored red curb without exception sign; firetruck and service worker'},
            'service_class': {'kind': 'world_setup', 'value': 'emergency_vehicle'},
            'sign_classes': {'kind': 'world_setup', 'value': []},
            'requested_parking_x_m': {'kind': 'controller', 'value': 40, 'unit': 'm'},
            'requested_stationary_duration_s': {'kind': 'controller',
                                                'value': 12, 'unit': 's'},
            'business_activity_request': {'kind': 'controller', 'value': True},
            'red_curb_stop_or_park': {'kind': 'subject_behavior', 'value': None}},
        'recording_description': construction['recording_description'],
        'unresolved_judgment_calls': [
            'Actual emergency vehicle identity, business purpose and necessary '
            'duration require independent source and legal review.'],
    }
    existing = {row['case_id']: row for row in document['cases']}
    if CASE in existing:
        if existing[CASE] != proposal:
            raise ValueError('Existing emergency business proposal differs')
        return {'case_id': CASE, 'added': False}
    document['cases'].append(proposal)
    PROPOSALS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return {'case_id': CASE, 'added': True}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
