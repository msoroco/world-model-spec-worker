"""Generate bounded law-specific textual software diagnostics for both cases."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
INPUT=REPO/'inputs'/ROOT.name/'assignment.json'


def sha_text(text):return hashlib.sha256(text.encode()).hexdigest()


def write_case(label):
    spec=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    files=spec['files']
    trace=[json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    if len(trace)!=9:raise ValueError('Pinned adapter scaffold changed frame count')
    context={'facing_head_id':7,'stop_line_x_m':-8.0,
             'intersection_bounds_m':[-5,-5,8,5],
             'adjacent_crosswalk_bounds_m':[[-8,-5,-5,5],[8,-5,11,5]],
             'diagnostic_only':True}
    files['intersection-context.json']=json.dumps(context,sort_keys=True)+'\n'
    xs=([-12,-10,-10,-10,-6,-2,2,8,12] if label=='yield' else
        [-12,-9,-6,-3,0,3,6,9,12])
    signal_rows=[];ego_rows=[];participant_rows=[]
    for index,(frame,x) in enumerate(zip(trace,xs)):
        ident={'frame':frame['frame'],'time_s':frame['time_s']}
        signal_rows.append(dict(ident,facing_head_id=7,aspect={
            'source_verified':True,'source_ref':'diagnostic signal-head text only',
            'head_id':7,'observed_frame':frame['frame'],
            'illuminated_indications':[{'color':'green','shape':'arrow','direction':'straight'}]}))
        ego_rows.append(dict(ident,body_vertices_m=[[x,-.5,0],[x+1,-.5,0],
                                                     [x+1,.5,0],[x,.5,0]],heading_deg=0))
        people=[]
        if label=='yield' and index in (0,1,2,3):
            people=[{'id':'pedestrian-1','role':'pedestrian','lawfully_present':True,
                     'lawful_presence_source':'diagnostic phase text only',
                     'body_vertices_m':[[-7,-.5,0],[-6,-.5,0],[-6,.5,0],[-7,.5,0]]}]
        elif label=='yield':
            people=[{'id':'pedestrian-1','role':'pedestrian','lawfully_present':True,
                     'lawful_presence_source':'diagnostic phase text only',
                     'body_vertices_m':[[-7,8,0],[-6,8,0],[-6,9,0],[-7,9,0]]}]
        participant_rows.append(dict(ident,participants=people))
    for name,rows in [('signal-head-history.jsonl',signal_rows),
                      ('ego-body-history.jsonl',ego_rows),
                      ('participant-history.jsonl',participant_rows)]:
        files[name]=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
    required=('signal-head-history.jsonl','ego-body-history.jsonl',
              'participant-history.jsonl','intersection-context.json')
    files['acquisition.json']=json.dumps({name:{'kind':'original_native','sha256':sha_text(files[name])}
                                          for name in required},sort_keys=True)+'\n'
    files['fixture-provenance.json']=json.dumps({
        'scope':'CPU software diagnostic with inherited adapter graphs and synthetic color frames',
        'case_specific_sources':list(required),'physical_acceptance_claimed':False},sort_keys=True)+'\n'
    path=ROOT/('diagnostic-'+label+'.json')
    path.write_text(json.dumps(spec,ensure_ascii=False,separators=(',',':'))+'\n')
    source=str(path.relative_to(REPO))
    recipe={'format':'worker-fixture-recipe','sources':[
            {'path':'diagnostic-input.json','source':str(INPUT.relative_to(REPO)),
             'sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest()}],
            'generator':{'source':source,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT/('diagnostic-'+label+'-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')
    print(label,path.stat().st_size)


if __name__=='__main__':
    for label in ('clear','yield'):write_case(label)
