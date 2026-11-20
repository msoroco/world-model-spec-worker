"""Three source-triggered controller alternatives for each lead-presence probe."""
import copy
import hashlib
import json
from pathlib import Path

from traffic_pair_entrypoint import TUNINGS

HERE=Path(__file__).resolve().parent
TRIGGERS={
    'near_lead': (
        ('lead longitudinal gap before near-zero speed',
         'gap falls below 6 m while ego remains moving',
         'Request braking with a larger lead gap'),
        ('lead-relative closing speed and gap',
         'predicted stop distance exceeds retained gap',
         'Use a lower assumed lead-relative deceleration'),
        ('ego speed before the first lead brake request',
         'ego speed exceeds 4 m/s on approach',
         'Reduce common-destination cruise speed')),
    'absent_lead': (
        ('remaining destination distance and ego speed',
         'ego overshoots the surveyed destination',
         'Use stronger destination deceleration'),
        ('ego speed on approach to destination',
         'ego approaches faster than a stable stop allows',
         'Reduce common-destination cruise speed'),
        ('distance to destination at near-zero speed',
         'ego does not settle within the nominal 0.8 m radius',
         'Increase destination stop radius')),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build(mode):
    draft=json.loads((HERE/('draft-'+mode+'-manifest.json')).read_text())
    entry=copy.deepcopy(draft['cases'][0])
    primary_path=HERE/entry['construction']
    primary=json.loads(primary_path.read_text())
    if sha(primary_path)!=entry['construction_sha256']:
        raise ValueError('Traffic-pair primary changed before fallback construction')
    entry['candidate_risk']={'status':'physical',
        'reason':'Destination settling and lead-relative closure need separate source-measured alternative controls.'}
    candidates=[]
    for i,(metric,failure,reason) in enumerate(TRIGGERS[mode],1):
        ident='fallback'+str(i)
        construction=copy.deepcopy(primary)
        config_file=next(item for item in construction['files']
                         if item['path']=='config.json')
        config=json.loads(config_file['content'])
        config['candidate_id']=ident
        config['traffic_pair_controller_tuning']=TUNINGS[mode][ident]
        config_file['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
        construction['status']='draft_fallback_cpu_preparation_incomplete'
        construction['candidate_id']=ident
        construction['mechanisms']=primary['mechanisms']+[
            ident+': '+reason+'; tuning '+json.dumps(TUNINGS[mode][ident],sort_keys=True)]
        name='draft-'+mode+'-'+ident+'-construction.json'
        write(HERE/name,construction)
        candidates.append({'id':ident,'construction':name,
            'construction_sha256':sha(HERE/name),
            'trigger':{'source':'native-actors.jsonl','metric':metric,
                       'failure_condition':failure},
            'changed_knobs':[key+': '+str(value)
                             for key,value in TUNINGS[mode][ident].items()]})
    entry['candidates']=candidates
    draft['cases']=[entry]
    draft['status']='draft_'+mode+'_four_candidate_diagnostic'
    manifest=HERE/('draft-'+mode+'-fallback-manifest.json')
    write(manifest,draft)
    return {'mode':mode,'manifest_sha256':sha(manifest),
            'candidates':{row['id']:row['construction_sha256']
                          for row in candidates}}


if __name__=='__main__':
    print(json.dumps([build(mode) for mode in ('near_lead','absent_lead')],sort_keys=True))
