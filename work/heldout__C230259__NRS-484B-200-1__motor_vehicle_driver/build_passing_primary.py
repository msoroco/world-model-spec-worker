"""Construct source-backed C230259 same-direction passing primary for offline proof."""
import json
from hashlib import sha256
from pathlib import Path
HERE=Path(__file__).resolve().parent
CASE=HERE.name+'__passing_left'
def sha(path):return sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    base=json.loads((HERE/'construction-baseline_left.json').read_text())
    base['case_id']=CASE;base['entrypoint']='passing_runner.py'
    base['mechanisms']['route']='connected right-to-left-to-right passing targets around same-direction lead'
    base['mechanisms']['control']='10 m/s ego target, slower lead, bounded feedback and terminal brake'
    base['mechanisms']['construction_status']='exact_passing_primary_offline_pending'
    base['static_checks']=['Exact C230259 passing-left identity, 80 original ticks at 20 Hz',
       'Connected two-way lead route with left excursion before lead and right return after',
       'Original body/road geometry and four named FFV1 source cameras']
    base['termination_rules']=['Stop after 80 original ticks',
       'Fail on missing actor, source frame or road-center geometry',
       'Close encoders and restore world settings']
    base['recording_description']['channels'][0]['time_window']='all original 80 frames'
    for item in base['files']:
        if item['path']=='config.json':
            config=json.loads(item['content'])
            config['selected_case_id']=CASE;config['supported_case_ids']=[CASE]
            config['case']['case_id']=CASE
            config['case']['recording_description']=base['recording_description']
            config['frames']=80;config['duration_s']=4
            item['content']=json.dumps(config,indent=2)+'\n'
        elif item['path']=='runner.py':
            item['path']='passing_runner.py';item['content']=(HERE/'passing_runner.py').read_text()
        elif item['path'].startswith('tests/'):
            item['path']='tests/test_passing_runner_config.py';item['content']=(HERE/item['path']).read_text()
    base['files']=list({item['path']: item for item in base['files']}.values())
    base['files'].append({'path':'right_half_passing.py','content':(HERE/'right_half_passing.py').read_text()})
    base['files'].append({'path':'tests/test_right_half_passing.py','content':(HERE/'tests/test_right_half_passing.py').read_text()})
    base['measurement_plan']['original_sources'].append('passing_setup from original lead actor and route')
    path=HERE/'construction-passing_left.json';write(path,base)
    manifest_path=HERE/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['cases']=[entry for entry in manifest['cases'] if entry['case_id']!=CASE]
    manifest['cases'].append({'case_id':CASE,'kind':'delivery',
        'construction':path.name,'construction_sha256':sha(path),
        'measurement_procedure':{'entrypoint':'right_half_finalizer.py'},
        'candidate_risk':{'status':'physical','reason':'Passing clearance, left excursion, right return and four-camera visibility need Native verification'},
        'candidates':[]})
    write(manifest_path,manifest)
    return {'case_id':CASE,'construction_sha256':sha(path)}
if __name__=='__main__':print(json.dumps(build()))
