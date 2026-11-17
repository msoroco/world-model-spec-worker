"""Bind four exact adjacent-mail/no-deposit draft candidates."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CASE='mail_adjacent_no_deposit'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source=json.loads((ROOT/'execution-manifest-diagnostic-emergency-no-business-draft.json').read_text())
    entry=source['cases'][0]
    entry['case_id']=ROOT.name+'__'+CASE
    entry['construction']='selected-primary/'+CASE+'/construction.json'
    entry['construction_sha256']=digest(ROOT/entry['construction'])
    entry['candidate_risk']['reason']=(
        'Ordinary vehicle may overshoot red paint; overview may hide its body '
        'or authored U.S. mail box; unexpected walker or parcel would invalidate no-deposit probe')
    for candidate in entry['candidates']:
        ident=candidate['id']
        candidate['construction']=f'selected-fallbacks/{CASE}/{ident}/construction.json'
        candidate['construction_sha256']=digest(ROOT/candidate['construction'])
        for field in ('source','metric','failure_condition'):
            candidate['trigger'][field]=candidate['trigger'][field].replace(
                'firetruck body','ordinary vehicle body')
    path=ROOT/'execution-manifest-diagnostic-mail-adjacent-no-deposit-draft.json'
    path.write_text(json.dumps(source,indent=2,allow_nan=False)+'\n')
    return {'case_id':entry['case_id'],'manifest':str(path.relative_to(ROOT)),
            'sha256':digest(path),'candidates':4}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
