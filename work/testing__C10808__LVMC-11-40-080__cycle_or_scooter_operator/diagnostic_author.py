"""Create two source-shaped C10808 software fixtures from the pinned example.

The example graphs and pixels are synthetic compatibility scaffolding. The
case-specific event stream is also synthetic and never physical/legal evidence.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO/'runtime/fixtures/example.json'
ASSIGNMENT = REPO/'inputs'/ROOT.name/'assignment.json'


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def body(x):
    return [[x-.2,-.2,0.],[x-.2,.2,0.],
            [x+.2,-.2,0.],[x+.2,.2,0.]]


def author(dismounted):
    template = json.loads(BASE.read_text())
    mapping = [json.loads(line) for line in template['files']['video_frames.jsonl'].splitlines()]
    phases = (['mounted_approach']*3+['dismount_hold']+
              ['afoot_reversal']*3+['turn_complete']*2 if dismounted else
              ['mounted_approach']*3+['mounted_reversal']*4+['turn_complete']*2)
    events=[]
    for index,(frame,phase) in enumerate(zip(mapping,phases)):
        human_x=(min(index,2) if phase in ('mounted_approach','dismount_hold')
                 else index-1) if dismounted else index
        bicycle_x=(min(index,2) if dismounted else index)
        heading=[0.,0.,0.,0.,45.,90.,135.,180.,180.][index]
        events.append({'frame':frame['carla_frame'],'time_s':frame['time_s'],
                       'phase':phase,'operator_id':'fixture-operator',
                       'bicycle_id':'fixture-bicycle','sign_id':'fixture-sign',
                       'heading_deg':heading,
                       'operator_body_vertices_m':body(human_x),
                       'bicycle_body_vertices_m':body(bicycle_x),
                       'sign_body_vertices_m':body(-8.),
                       'body_source':'synthetic diagnostic body geometry'})
    files=template['files']
    files['phase-events.jsonl']=''.join(json.dumps(row)+'\n' for row in events)
    files['sign-authorization-source']='Synthetic source placeholder; no authorization established.\n'
    files['sign-inventory.json']=json.dumps({
        'message':'NO U TURN','erected':True,'sign_actor_id':'fixture-sign',
        'authorization_source_sha256':sha_bytes(files['sign-authorization-source'].encode()),
        'authorization_status':'unresolved_diagnostic_only'})+'\n'
    required=('phase-events.jsonl','sign-inventory.json',
              'sign-authorization-source','video_frames.jsonl')
    files['acquisition.json']=json.dumps({name:{'kind':'original_native',
        'sha256':sha_bytes(files[name].encode())} for name in required})+'\n'
    files['fixture-provenance.json']=json.dumps({'diagnostic_fixture':True,
        'scope':'Synthetic C10808 software compatibility only; no physical or legal claim'})+'\n'
    suffix='dismount_before_uturn' if dismounted else 'mounted_uturn'
    diagnostic=ROOT/('diagnostic-'+suffix+'.json')
    diagnostic.write_text(json.dumps(template,separators=(',',':'))+'\n')
    recipe={'format':'worker-fixture-recipe','sources':[
        {'path':'diagnostic-input.json','source':str(ASSIGNMENT.relative_to(REPO)),
         'sha256':sha(ASSIGNMENT)},
        {'path':'diagnostic-base.json','source':str(BASE.relative_to(REPO)),
         'sha256':sha(BASE)}],
        'generator':{'source':str(diagnostic.relative_to(REPO)),
                     'sha256':sha(diagnostic)}}
    (ROOT/('diagnostic-'+suffix+'-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')


if __name__=='__main__':
    author(True)
    author(False)
