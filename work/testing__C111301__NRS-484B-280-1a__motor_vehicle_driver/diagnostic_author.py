"""Build bounded text diagnostics; these never establish physical acceptance."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def body(x,y):return [[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]


def write_case(label):
    fixture=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    files=fixture['files']
    trace=[json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    if len(trace)!=9:raise ValueError('Pinned fixture frame count changed')
    context={'route_source':'diagnostic/ego-route','manual_wheelchair_asset_source':'diagnostic/manual-chair',
             'intersection_bounds_m':[-5,-5,8,5],'diagnostic_only':True}
    files['intersection-context.json']=json.dumps(context,sort_keys=True)+'\n'
    rows=[]
    for i,frame in enumerate(trace):
        x=-8+i*2
        y=0 if label=='crossing' else 5
        ego=body(x,0);chair=body(0,y)
        nearest=max(0,-(x+1)) if label=='crossing' else 4
        # Controller and actor values are diagnostic text, never Native observations.
        from runner import gap
        measured=gap(ego,chair)
        rows.append({'frame':frame['frame'],'time_s':frame['time_s'],
          'ego_body_vertices_m':ego,'ego_speed_mps':4,'ego_brake':int(label=='crossing' and i>=2),
          'person':{'role':'person_in_manual_wheelchair','source_ref':'diagnostic/person',
                    'body_vertices_m':chair},
          'manual_wheelchair':{'kind':'manual_wheelchair','source_ref':'diagnostic/chair',
                               'body_vertices_m':chair},
          'surface_gap_m':measured,'contact_event':False})
    files['encounter-history.jsonl']=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
    names=('encounter-history.jsonl','intersection-context.json')
    files['acquisition.json']=json.dumps({name:{'kind':'original_native','sha256':sha(files[name])}
                                         for name in names},sort_keys=True)+'\n'
    files['fixture-provenance.json']=json.dumps({'scope':'CPU software diagnostic with synthetic source text and inherited adapter frames',
        'case_specific_sources':list(names),'physical_acceptance_claimed':False})+'\n'
    path=ROOT/('diagnostic-'+label+'.json')
    path.write_text(json.dumps(fixture,ensure_ascii=False,separators=(',',':'))+'\n')
    source=str(path.relative_to(REPO))
    assignment=REPO/'inputs'/ROOT.name/'assignment.json'
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
        'source':str(assignment.relative_to(REPO)),'sha256':hashlib.sha256(assignment.read_bytes()).hexdigest()}],
        'generator':{'source':source,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT/('diagnostic-'+label+'-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')


if __name__=='__main__':
    for label in ('clear','crossing'):write_case(label)
