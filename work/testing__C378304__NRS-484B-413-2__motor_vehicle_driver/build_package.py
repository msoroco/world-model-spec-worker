"""Freeze exact 100-foot signal-distance probes with measured source analysis."""
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
    assert assignment['law']['id']==plan['law_id']=='NRS-484B-413-2'
    assert [c['target_type'] for c in plan['cases']]==['baseline','boundary_probe','boundary_probe','boundary_probe']
    cases=copy.deepcopy(plan['cases'])
    for case in cases:
        case['variable_assignments']['highway_context']['value']['administrative_status']='explicit synthetic business-district and public-way assumptions; frontage objects separately measured'
    plan['cases']=cases
    plan['sources']=[{'path':rel,'sha256':sha(REPO/rel)} for rel in [
        'inputs/'+AID+'/assignment.json','runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'runtime/main-pipeline-v1/capabilities/verify_recorded_indicators.py',
        'updates/004.json','skills/scenario-coverage-cases/SKILL.md']]
    plan['runtime_uncertainties']=['Actual continuous API-indicator distance before trajectory-derived course change is unmeasured.',
        'Right-lamp pixel ROI and blinking need calibration against actual original source frames.',
        'Business-district use is an explicit synthetic assumption; authored frontage/loading objects need native and visual readback.',
        'Native turn tracking, capture completeness, camera visibility and final encoded-video checks need first-run evidence.']
    write(FOLDER/'case-plan.json',plan)
    write(FOLDER/'proposals/cases.json',{'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],
        'cases':cases,'sweep_specs':[],'sweeps_expanded':True})
    base=json.loads((CANDIDATE/'config.json').read_text())
    base['supported_case_ids']=[c['case_id'] for c in cases]
    base['required_atoms']=[o['name'] for o in plan['observations'] if o.get('mandatory',True)]
    base['max_ticks']=600;base['implementation_gaps']=[]
    base['right_lamp_roi_px']=[950,580,150,100]
    base['authored_test_context']={'core_assumptions':[
        'Public-way and business-district status are explicit synthetic assumptions.',
        'Business frontage and freight-loading-zone physical objects are authored in scenario.py and require native/pixel confirmation.',
        'The target statutory distance is 100 feet = 30.48m; requested trigger is distinct from measured traveled distance.']}
    files=['runner.py','scenario.py','intersection.xodr','source_audit.py','analyze.py','tests/test_signal.py'];entries=[]
    for case in cases[1:]:
        cfg=copy.deepcopy(base);cfg['case']=case;cfg['selected_case_id']=case['case_id']
        construction={'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],
            'entrypoint':'runner.py','recording_description':case['recording_description'],
            'measurement_plan':{'source':'physical_samples.jsonl and view0.mkv','threshold_m':30.48,
                'method':'continuous actual API signal onset to trajectory-derived turn onset, integrated original positions and decoded right-lamp ROI',
                'sampling_hz':20,'target_commanded_m':case['variable_assignments']['commanded_signal_distance']['value']},
            'static_checks':['two-directional OpenDRIVE intersection','business frontage/loading object declarations',
                'right-turn route continuity','four camera formats','mandatory channels'],
            'termination_rules':{'max_ticks':600,'success':'right-turn route end reached','failure':'timeout or capture error'},
            'mechanisms':{'builder':'scenario.py OpenDRIVE intersection and frontage',
                'controller':'native VehicleControl and VehicleLightState.RightBlinker',
                'capture':'supplied PipelineCapture with original observations',
                'video':'four lossless FFV1 Matroska source views with frame/pixel hashes'},
            'files':[{'path':f,'content':(FOLDER/f).read_text(),'source':'work/'+AID+'/'+f} for f in files]+
                    [{'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'}]}
        rel='constructions/'+case['case_id']+'.json';write(FOLDER/rel,construction)
        if case is cases[1]:write(FOLDER/'config.json',cfg);write(FOLDER/'construction.json',construction)
        entries.append({'case_id':case['case_id'],'kind':'capability','construction':rel,
            'construction_sha256':sha(FOLDER/rel),
            'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'right-signal-distance-capability-v1'}})
    write(FOLDER/'execution-manifest.json',{'format':'worker-execution-manifest-v1','assignment_id':AID,
        'runtime_manifest_sha256':sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),'cases':entries})


if __name__=='__main__':main()
