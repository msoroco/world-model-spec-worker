"""Add the adjacent-box/no-deposit diagnostic semantic proposal."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OLD=ROOT.name+'__mail_adjacent_deposit'
CASE=ROOT.name+'__mail_adjacent_no_deposit'


def build():
    path=ROOT/'proposals/cases.json'
    document=json.loads(path.read_text())
    prior=next(row for row in document['cases'] if row['case_id']==OLD)
    proposal=json.loads(json.dumps(prior))
    proposal['case_id']=CASE
    proposal['rationale']=(
        'Request the same ordinary red-curb 12-second stop beside the authored '
        'U.S. mail box without a mail worker or parcel action. Empty retained '
        'inventories are a diagnostic no-activity proxy; actual absence and '
        'legal exception remain unverified.')
    proposal['variable_assignments']['road_and_actors']['value']=(
        'red curb with authored adjacent U.S. mail box; ordinary vehicle and empty worker/parcel inventories')
    proposal['variable_assignments']['mail_deposit_request']['value']=False
    construction=json.loads((ROOT/'selected-primary/mail_adjacent_no_deposit/construction.json').read_text())
    proposal['recording_description']=construction['recording_description']
    proposal['unresolved_judgment_calls']=[
        'Empty retained walker and parcel inventories do not prove no real-world '
        'mail activity; original Native and pixel review remains necessary.']
    existing={row['case_id']:row for row in document['cases']}
    if CASE in existing:
        if existing[CASE]!=proposal:
            raise ValueError('Existing no-deposit proposal differs')
        return {'case_id':CASE,'added':False}
    document['cases'].append(proposal)
    path.write_text(json.dumps(document,indent=2,ensure_ascii=False)+'\n')
    return {'case_id':CASE,'added':True}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
