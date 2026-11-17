"""Add the exact adjacent U.S. mail drop diagnostic proposal."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + '__mail_adjacent_deposit'


def build():
    path = ROOT / 'proposals/cases.json'
    document = json.loads(path.read_text())
    plan = next(row for row in json.loads((ROOT / 'exception-case-matrix.json').read_text())['cases']
                if row['case_id'] == CASE)
    if (plan['service_class'], plan['mailbox_requested'], plan['activity_request']) != (
            'ordinary', True, 'mail_deposit'):
        raise ValueError('Frozen mail-drop scope differs')
    construction = json.loads((ROOT / 'selected-primary/mail_adjacent_deposit/construction.json').read_text())
    proposal = {'case_id': CASE, 'target_law_id': 'LVMC-11-52-030-A',
        'target_type': 'attempt',
        'rationale': ('Request an ordinary vehicle stopped for 12 seconds beside an '
            'authored U.S. mail drop box. A worker and attached parcel approach the '
            'drop location; parcel disappearance is a diagnostic activity proxy. '
            'Original placement, mailbox rendering, expeditiousness and legal '
            'outcome remain unverified.'),
        'variable_assignments': {
            'road_and_actors': {'kind':'world_setup',
                'value':'red curb with authored adjacent U.S. mail box; ordinary vehicle, worker and parcel prop'},
            'service_class': {'kind':'world_setup','value':'ordinary'},
            'sign_classes': {'kind':'world_setup','value':[]},
            'mailbox_requested': {'kind':'world_setup','value':True},
            'requested_parking_x_m': {'kind':'controller','value':40,'unit':'m'},
            'requested_stationary_duration_s': {'kind':'controller','value':12,'unit':'s'},
            'mail_deposit_request': {'kind':'controller','value':True},
            'red_curb_stop_or_park': {'kind':'subject_behavior','value':None}},
        'recording_description': construction['recording_description'],
        'unresolved_judgment_calls': ['Actual U.S. mail placement, adjacency and '
            'expeditiousness require original source and legal review.']}
    existing = {row['case_id']: row for row in document['cases']}
    if CASE in existing:
        if existing[CASE] != proposal:
            raise ValueError('Existing mail proposal differs')
        return {'case_id': CASE, 'added': False}
    document['cases'].append(proposal)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return {'case_id': CASE, 'added': True}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
