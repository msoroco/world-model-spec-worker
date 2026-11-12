"""Source-shaped diagnostic for the exact passing-left CPU software path."""
import json
from hashlib import sha256
from pathlib import Path
HERE=Path(__file__).resolve().parent
CASE=HERE.name+'__passing_left'
def sha(path):return sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    contract=json.loads((HERE/'measurement-contract-baseline_right.json').read_text())
    contract['case_id']=CASE
    write(HERE/'measurement-contract-passing_left.json',contract)
    proposal_path=HERE/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
    row=json.loads(json.dumps(proposal['cases'][0]));row['case_id']=CASE
    row['rationale']='Original full-body right-to-left-to-right passing attempt around same-direction lead, with governing-law review unresolved.'
    row['variable_assignments']={
        'passing_path':{'kind':'controller','value':'right_left_right'},
        'lead_spawn_station':{'kind':'world_setup','value':8},
        'governing_passing_law_satisfied':{'kind':'subject_behavior','value':None}}
    construction=json.loads((HERE/'construction-passing_left.json').read_text())
    row['recording_description']=construction['recording_description']
    proposal['cases']=[entry for entry in proposal['cases'] if entry['case_id']!=CASE]+[row]
    write(proposal_path,proposal)
    diagnostic=json.loads((HERE/'diagnostic-baseline_right.json').read_text())
    lateral=[-2.,-2.,-2.,-1.,0.,2.,2.,0.,-2.]
    body=[json.loads(line) for line in diagnostic['files']['ego_road_frames.jsonl'].splitlines() if line]
    trace=[json.loads(line) for line in diagnostic['files']['trace.jsonl'].splitlines() if line]
    evidence=[json.loads(line) for line in diagnostic['files']['capture/evidence.jsonl'].splitlines() if line]
    if len(body)!=len(trace) or len(body)!=len(lateral) or len(evidence)!=len(body):
        raise ValueError('Passing diagnostic original frame inventory differs')
    for i,(frame,sample,packet,y) in enumerate(zip(body,trace,evidence,lateral)):
        x=sample['position']['x']
        frame['lane_id']=1 if y>0 else -1
        frame['ego_corners_xy']=[[x-2.4,y-.9],[x+2.4,y-.9],[x+2.4,y+.9],[x-2.4,y+.9]]
        sample['position']['y']=y;sample['position_m'][1]=y
        packet['ego']['position_m'][1]=y
        if 'body_vertices_m' in packet['ego']:
            original_y=evidence[i]['ego']['body_vertices_m'][0][1]
            for vertex in packet['ego']['body_vertices_m']:
                vertex[1]+=y-original_y
    diagnostic['files']['ego_road_frames.jsonl']=''.join(json.dumps(row)+'\n' for row in body)
    diagnostic['files']['trace.jsonl']=''.join(json.dumps(row)+'\n' for row in trace)
    diagnostic['files']['capture/evidence.jsonl']=''.join(json.dumps(row)+'\n' for row in evidence)
    capture_manifest=json.loads(diagnostic['files']['capture/manifest.json'])
    capture_manifest['case_id']=CASE
    capture_manifest['sources']['trace.jsonl']=sha256(diagnostic['files']['trace.jsonl'].encode()).hexdigest()
    diagnostic['files']['capture/manifest.json']=json.dumps(capture_manifest,indent=2)+'\n'
    context=json.loads(diagnostic['files']['road_exception_context.json'])
    context['passing_setup']={'same_direction_lead_route_station':8,
                              'subject_path':'right_left_right',
                              'governing_passing_law_review':'undecided'}
    diagnostic['files']['road_exception_context.json']=json.dumps(context)+'\n'
    spec=HERE/'diagnostic-passing_left.json'
    spec.write_text(json.dumps(diagnostic,separators=(',',':'))+'\n')
    ref='work/'+HERE.name+'/'+spec.name
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':ref,'sha256':sha(spec)}],
            'generator':{'source':ref,'sha256':sha(spec)}}
    write(HERE/'fixture-recipe-passing_left.json',recipe)
    manifest_path=HERE/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
    entry=next(item for item in manifest['cases'] if item['case_id']==CASE)
    entry['measurement_contract']='measurement-contract-passing_left.json'
    entry['fixture_recipe']='work/'+HERE.name+'/fixture-recipe-passing_left.json'
    write(manifest_path,manifest)
    return {'diagnostic_bytes':spec.stat().st_size,'diagnostic_sha256':sha(spec)}
if __name__=='__main__':print(json.dumps(build()))
