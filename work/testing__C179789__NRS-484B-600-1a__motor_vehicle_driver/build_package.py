"""Freeze exported physical speed grid without a reasonable-speed cutoff."""
import copy
import hashlib
import json
import sys
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
REPO=FOLDER.parents[1]
AID=FOLDER.name
CANDIDATE=REPO/'migration-candidates'/AID
sys.path.insert(0,str(REPO/'runtime/main-pipeline-v1/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n')


def main():
    assignment=json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    plan=json.loads((CANDIDATE/'case-plan.json').read_text())
    assert assignment['law']['id']==plan['law_id']=='NRS-484B-600-1a'
    assert len(plan['cases'])==1 and plan['cases'][0]['target_type']=='baseline'
    baseline=plan['cases'][0]
    assignments=copy.deepcopy(baseline['variable_assignments'])
    assignments['test_branch']['value']='physical_speed_sweep'
    assignments['highway_context']['value']['administrative_status']='explicit synthetic public-highway assumption'
    assignments['commanded_speed_mps']={'kind':'controller','value':5.0,'unit':'m/s'}
    sweep={'sweep_id':AID+'__speed', 'target_law_id':assignment['law']['id'],
        'judgment_refs':[{'phrase':'reasonable or proper','note':'Unresolved statutory speed judgment'}],
        'status':'complete','mode':'one_dimensional',
        'rationale':'Fixed traffic, paved surface, road width and weather; sample requested ego speeds without a legal cutoff',
        'axes':[{'variable':'commanded_speed_mps','observable':'realized_mean_speed_mps','unit':'m/s',
            'min':5.0,'max':20.0,'spacing':5.0,
            'range_rationale':'A 500m route and 30s episode can request 5–20m/s; actual vehicle realization is the capability question',
            'spacing_rationale':'5m/s controller increments exceed 20Hz speed sampling noise; no legal standard is inferred',
            'feasibility_evidence':'Native VehicleControl target-speed controller and a 500m paved-road construction are executable; physical bounds unverified',
            'measurement':{'method':'mean original actor.get_velocity magnitude across native x=100..300m; full raw stream retained',
                           'time_window':'ego x=100..300m','statistic':'mean'}}],
        'landmarks':[],'variable_assignments':assignments,'recording_description':baseline['recording_description']}
    proposal={'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],
              'cases':[baseline],'sweep_specs':[sweep]}
    expand_sweeps(proposal,templates=(),bindings=None)
    cases=proposal['cases'];plan['cases']=cases;plan['comparisons']=[]
    plan['sources']=[{'path':rel,'sha256':sha(REPO/rel)} for rel in [
        'inputs/'+AID+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'runtime/main-pipeline-v1/scenario_pipeline/batch_pipeline/sweeps.py','updates/004.json',
        'skills/scenario-coverage-cases/SKILL.md']]
    plan['runtime_uncertainties']=['Realized speed and traffic state over the full trace are unmeasured.',
        'Paved surface, native lane width, controller tracking, camera visibility, and duration need capture.',
        'Reasonable or proper remains an unresolved legal judgment; no speed threshold is asserted.']
    write(FOLDER/'case-plan.json',plan);write(FOLDER/'proposals/cases.json',proposal)
    base=json.loads((CANDIDATE/'config.json').read_text())
    base['supported_case_ids']=[c['case_id'] for c in cases]
    base['required_atoms']=[o['name'] for o in plan['observations'] if o.get('mandatory',True)]
    base['max_ticks']=600;base['implementation_gaps']=[]
    base['authored_test_context']={'core_assumptions':['Public highway status is an explicit synthetic assumption.',
        'Paved two-lane 500m road, clear weather and adjacent-lane traffic are fixed across sweep points.',
        'No legal reasonable-speed threshold or label is authored.']}
    files=['runner.py','scenario.py','source_audit.py','analyze.py','tests/test_speed.py'];entries=[]
    for case in cases[1:]:
        cfg=copy.deepcopy(base);cfg['case']=case;cfg['selected_case_id']=case['case_id']
        construction={'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
            'entrypoint':'runner.py','recording_description':case['recording_description'],
            'measurement_plan':{'source':'physical_samples.jsonl','method':'actual 20Hz ego speed over x=100..300m; other traffic state retained',
                                'requested_mps':case['variable_assignments']['commanded_speed_mps']['value']},
            'static_checks':['paved OpenDRIVE length and lane width','route continuity','four camera formats','mandatory channels'],
            'termination_rules':{'max_ticks':600,'success':'ego route end reached','failure':'timeout or capture error'},
            'mechanisms':{'builder':'scenario.py OpenDRIVE','controllers':'native VehicleControl for ego and adjacent traffic',
                'capture':'supplied PipelineCapture and original observations',
                'video':'four lossless FFV1 Matroska source views with frame/pixel hashes'},
            'files':[{'path':f,'content':(FOLDER/f).read_text(),'source':'work/'+AID+'/'+f} for f in files]+
                    [{'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'}]}
        rel='constructions/'+case['case_id']+'.json';write(FOLDER/rel,construction)
        if case is cases[1]:write(FOLDER/'config.json',cfg);write(FOLDER/'construction.json',construction)
        entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
            'construction_sha256':sha(FOLDER/rel),
            'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'reasonable-speed-capability-v1'}})
    write(FOLDER/'execution-manifest.json',{'format':'worker-execution-manifest-v1',
        'assignment_id':AID,'runtime_manifest_sha256':sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
        'cases':entries})


if __name__=='__main__':main()
