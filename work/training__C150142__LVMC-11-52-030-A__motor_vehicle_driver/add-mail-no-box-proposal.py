"""Add the controlled no-box mail activity attempt proposal."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OLD=ROOT.name+'__mail_adjacent_deposit'
CASE=ROOT.name+'__mail_no_box_deposit'


def build():
    path=ROOT/'proposals/cases.json'
    document=json.loads(path.read_text())
    prior=next(row for row in document['cases'] if row['case_id']==OLD)
    proposal=json.loads(json.dumps(prior))
    proposal['case_id']=CASE
    proposal['rationale']=(
        'Repeat the ordinary red-curb 12-second worker and parcel-disappearance '
        'attempt at the same x=40 drop location without an authored adjacent '
        'U.S. mail box. This isolates box presence; actual U.S. mail deposit, '
        'expeditiousness and legal outcome remain unverified.')
    proposal['variable_assignments']['road_and_actors']['value']=(
        'red curb without adjacent U.S. mail box; ordinary vehicle, worker and parcel prop')
    proposal['variable_assignments']['mailbox_requested']['value']=False
    construction=json.loads((ROOT/'selected-primary/mail_no_box_deposit/construction.json').read_text())
    proposal['recording_description']=construction['recording_description']
    proposal['unresolved_judgment_calls']=[
        'The absent adjacent U.S. mail box and parcel-disappearance proxy do '
        'not establish actual U.S. mail deposit or statutory expeditiousness.']
    existing={row['case_id']:row for row in document['cases']}
    if CASE in existing:
        if existing[CASE]!=proposal:
            raise ValueError('Existing no-box proposal differs')
        return {'case_id':CASE,'added':False}
    document['cases'].append(proposal)
    path.write_text(json.dumps(document,indent=2,ensure_ascii=False)+'\n')
    return {'case_id':CASE,'added':True}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
