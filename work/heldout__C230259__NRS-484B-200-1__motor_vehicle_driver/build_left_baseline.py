"""Build the exact opposite-side baseline from the proved right-side contract."""
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ASSIGNMENT=HERE.name
CASE=ASSIGNMENT+'__baseline_left'

def sha(path): return sha256(path.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    primary=json.loads((HERE/'construction.json').read_text())
    primary['case_id']=CASE
    for item in primary['files']:
        if item['path']=='config.json':
            config=json.loads(item['content'])
            config['selected_case_id']=CASE
            config['supported_case_ids']=[CASE]
            config['case']['case_id']=CASE
            item['content']=json.dumps(config,indent=2)+'\n'
    write(HERE/'construction-baseline_left.json',primary)
    contract=json.loads((HERE/'measurement-contract-baseline_right.json').read_text())
    contract['case_id']=CASE
    write(HERE/'measurement-contract-baseline_left.json',contract)
    diagnostic=json.loads((HERE/'diagnostic-baseline_right.json').read_text())
    frames=[json.loads(s) for s in diagnostic['files']['ego_road_frames.jsonl'].splitlines() if s]
    for frame in frames:
        frame['lane_id']=1
        frame['ego_corners_xy']=[[point[0],point[1]+4.] for point in frame['ego_corners_xy']]
    diagnostic['files']['ego_road_frames.jsonl']=''.join(json.dumps(row)+'\n' for row in frames)
    (HERE/'diagnostic-baseline_left.json').write_text(json.dumps(diagnostic,separators=(',',':'))+'\n')
    ref='work/'+ASSIGNMENT+'/diagnostic-baseline_left.json'
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':ref,'sha256':sha(HERE/'diagnostic-baseline_left.json')}],
            'generator':{'source':ref,'sha256':sha(HERE/'diagnostic-baseline_left.json')}}
    write(HERE/'fixture-recipe-baseline_left.json',recipe)
    proposals=json.loads((HERE/'proposals/cases.json').read_text())
    row=json.loads(json.dumps(proposals['cases'][0]))
    row['case_id']=CASE
    row['rationale']='Whole-body left-half baseline on same source-observed two-way road; no exception premise decided.'
    row['variable_assignments']['body_side']['value']='left'
    proposals['cases'].append(row)
    write(HERE/'proposals/cases.json',proposals)
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry={'case_id':CASE,'kind':'delivery','construction':'construction-baseline_left.json',
           'construction_sha256':sha(HERE/'construction-baseline_left.json'),
           'measurement_procedure':{'entrypoint':'right_half_finalizer.py'},
           'candidate_risk':{'status':'physical','reason':'Opposite-side body motion, two-way map geometry and source-camera visibility require Native verification'},
           'candidates':[],
           'measurement_contract':'measurement-contract-baseline_left.json',
           'fixture_recipe':'work/'+ASSIGNMENT+'/fixture-recipe-baseline_left.json'}
    manifest['cases'].append(entry)
    write(manifest_path,manifest)
    return {'case_id':CASE,'construction_sha256':entry['construction_sha256'],
            'diagnostic_bytes':(HERE/'diagnostic-baseline_left.json').stat().st_size}
if __name__=='__main__': print(json.dumps(build()))
