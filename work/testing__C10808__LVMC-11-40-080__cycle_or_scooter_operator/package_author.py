"""Bind the C10808 exact cases to selected measurements and diagnostic sources."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def description():
    channels=[]
    for name,method in (
        ('operator_pose','Original Native operator body envelope per frame'),
        ('bicycle_pose','Original Native bicycle body envelope per frame'),
        ('sign_inventory','Source-bound sign identity and authorization-source hash per frame'),
        ('phase_events','Constructed phase label joined to original frame and body state')):
        channels.append({'name':name,'unit':'structured record',
            'sampling_rate_hz':20,'method':method,'time_window':'entire 30 s U-turn attempt',
            'reference_frame':'original CARLA frame and elapsed time',
            'uncertainty':'20 Hz sampling and simulator body geometry; physical recognition pending'})
    return {'channels':channels,'context_inputs':[],
            'limitations':['Sign authorization, visible rider contact and pedestrian duties require independent source review; no legal verdict.']}


def main():
    manifest=json.loads(MANIFEST.read_text())
    manifest['runtime_manifest_sha256']=json.loads((REPO/'batch.json').read_text())['runtime']['source_manifest_sha256']
    plan=json.loads((ROOT/'case-plan.json').read_text())
    required=plan['requirement_dispositions'][0]
    contract={'format':'worker-measurement-contract','requirements':[
        {'disposition_index':0,'requirement':required['requirement'],
         'source':required['source'],'output_key':'dismount_turn_measurement',
         'method':'finalize','kind':'measured','value_type':'object',
         'inputs':['phase-events.jsonl','sign-inventory.json',
                   'sign-authorization-source','video_frames.jsonl']}],
         'negative':{'remove':['phase-events.jsonl'],
                     'error_contains':'Missing required source: phase-events.jsonl'}}
    write(ROOT/'measurement-contract.json',contract)
    proposal_cases=[]
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        path=ROOT/entry['construction']
        construction=json.loads(path.read_text())
        construction['recording_description']=description()
        for item in construction['files']:
            if item['path']=='config.json':
                config=json.loads(item['content'])
                config['physical_completion']={
                    'criterion':'turn','motion_source':'phase-events.jsonl',
                    'body_key':'operator_body_vertices_m','heading_key':'heading_deg',
                    'turn_degrees':180,'turn_tolerance_deg':30,
                    'minimum_progress_m':1.0,
                    'engineering_tolerances_not_legal':True}
                item['content']=json.dumps(config,indent=2)+'\n'
                if suffix=='dismount_before_uturn':
                    (ROOT/'config.json').write_text(item['content'])
        write(path,construction)
        entry['construction_sha256']=sha(path)
        entry.pop('offline',None)
        entry.pop('compatibility',None)
        entry.pop('post_capture',None)
        entry['measurement_contract']='measurement-contract.json'
        entry['measurement_procedure']={'entrypoint':'analysis.py'}
        entry['fixture_recipe']=str((ROOT/('diagnostic-'+suffix+'-recipe.json')).relative_to(REPO))
        entry['acquisition']={name:{'entrypoint':'analysis.py',
            'method':'Source-hashed original Native phase events and sign inventory projected by saved finalizer',
            'evidence':'channels/'+name+'.jsonl'}
            for name in ('operator_pose','bicycle_pose','sign_inventory','phase_events')}
        entry['native_handoff']={'python_env_var':'CARLA_PYTHON',
            'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}
        case=next(row for row in plan['cases'] if row['case_id']==entry['case_id'])
        proposal_cases.append(dict(case,target_type=(
            'compliant_attempt' if suffix=='dismount_before_uturn' else 'violating_attempt'),
            rationale='Planned physical exception comparison; sign authorization and pedestrian duties require source review, and no legal verdict is asserted.',
            paired_probe_id='uturn_dismount_exception',
            deliberate_differences=['dismount_before_turn'],
            probe={'primary_variable':'dismount_before_turn',
                   'comparison_or_standard':'Dismount exception against otherwise mounted turn at the same sign',
                   'target_value_or_branch':suffix},
            variable_assignments={'dismount_before_turn':{
                'kind':'controller','value':suffix=='dismount_before_uturn'}},
            recording_description=construction['recording_description'],
            unresolved_judgment_calls=[]))
    baseline=dict(proposal_cases[0],
        case_id=ROOT.name+'__baseline',target_law_id=None,target_type='baseline',
        rationale='Shared physical setup before the planned comparison; no legal verdict.',
        purpose='Shared alley and prohibited-turn sign setup',gap_ids=[])
    for key in ('paired_probe_id','deliberate_differences','probe'):
        baseline.pop(key,None)
    write(ROOT/'proposals/cases.json',{'cell_id':'C10808','actor':'cycle_or_scooter_operator',
        'status':'draft','cases':[baseline]+proposal_cases,'sweep_specs':[],
        'sweeps_expanded':False})
    write(MANIFEST,manifest)


if __name__=='__main__':main()
