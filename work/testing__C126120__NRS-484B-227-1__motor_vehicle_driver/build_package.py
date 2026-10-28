"""Freeze three median U-turn branch capability cases."""
import copy
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
REPO=FOLDER.parents[1]
AID=FOLDER.name
CANDIDATE=REPO/'migration-candidates'/AID


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n')


def main():
    assignment=json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    plan=json.loads((CANDIDATE/'case-plan.json').read_text())
    assert assignment['law']['id']==plan['law_id']=='NRS-484B-227-1'
    assert [c['target_type'] for c in plan['cases']]==['baseline','compliant_attempt','violating_attempt','compliant_attempt']
    cases=copy.deepcopy(plan['cases'])
    for case in cases:
        case['variable_assignments']['highway_context']['value']['administrative_status']='explicit synthetic public-highway and authority-established-opening assumption'
    plan['cases']=cases
    plan['sources']=[{'path':rel,'sha256':sha(REPO/rel)} for rel in [
        'inputs/'+AID+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'runtime/main-pipeline-v1/capabilities/catalogue.json','updates/004.json',
        'skills/scenario-coverage-cases/SKILL.md']]
    plan['runtime_uncertainties']=['Authored OpenDRIVE barrier objects may not create a raised collidable native median; ray and collision surveys are executable.',
        'Actual full-body divider/opening passage, reversing, tracking, camera visibility, and duration are unmeasured.',
        'Public authority establishment remains an explicit synthetic assumption separate from the physical opening.']
    write(FOLDER/'case-plan.json',plan)
    write(FOLDER/'proposals/cases.json',{'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],
        'cases':cases,'sweep_specs':[],'sweeps_expanded':True})
    base=json.loads((CANDIDATE/'config.json').read_text())
    base['supported_case_ids']=[c['case_id'] for c in cases]
    base['required_atoms']=[o['name'] for o in plan['observations'] if o.get('mandatory',True)]
    base['max_ticks']=600;base['implementation_gaps']=[]
    base['authored_test_context']={'core_assumptions':[
        'Public-highway status and public-authority establishment of the opening are explicit synthetic assumptions.',
        'Two separated right-hand carriageways, intact divider segments x=0..190 and x=220..400, and opening x=190..220 are authored.',
        'Native raised/collidable barrier status must be determined by physical surface rays, collision events, original pixels, and full-body samples.']}
    files=['runner.py','scenario.py','analyze.py','tests/test_median.py'];entries=[]
    for case in cases[1:]:
        cfg=copy.deepcopy(base);cfg['case']=case;cfg['selected_case_id']=case['case_id']
        construction={'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
            'entrypoint':'runner.py','recording_description':case['recording_description'],
            'measurement_plan':{'source':'native-setup.json and physical_samples.jsonl',
                'surface_rays_xy_m':[[150,10],[205,10],[250,10]],'opening_x_m':[190,220],
                'method':'topmost native surface hits, collision event stream, full original body vertices through median'},
            'static_checks':['OpenDRIVE carriageways and arc connector','authored intact segments/opening',
                'branch route continuity','four camera formats','mandatory channels'],
            'termination_rules':{'max_ticks':600,'success':'U-turn route endpoint reached',
                'failure':'collision, timeout or capture error; retained evidence is diagnostic'},
            'mechanisms':{'builder':'scenario.py OpenDRIVE roads/barrier objects',
                'controller':'native VehicleControl U-turn; reverse phase for multiple movement',
                'capture':'supplied PipelineCapture plus native surface/collision survey',
                'video':'four lossless FFV1 Matroska source views with frame/pixel hashes'},
            'files':[{'path':f,'content':(FOLDER/f).read_text(),'source':'work/'+AID+'/'+f} for f in files]+
                    [{'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'}]}
        rel='constructions/'+case['case_id']+'.json';write(FOLDER/rel,construction)
        if case is cases[1]:write(FOLDER/'config.json',cfg);write(FOLDER/'construction.json',construction)
        entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
            'construction_sha256':sha(FOLDER/rel),
            'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'median-opening-capability-v1'}})
    write(FOLDER/'execution-manifest.json',{'format':'worker-execution-manifest-v1','assignment_id':AID,
        'runtime_manifest_sha256':sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),'cases':entries})


if __name__=='__main__':main()
