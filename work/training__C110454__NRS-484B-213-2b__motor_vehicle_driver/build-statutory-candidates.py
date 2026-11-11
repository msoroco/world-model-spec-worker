"""Build exact unselected railroad and one-way Native alternatives."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NATIVE=HERE/'native'
sys.path.insert(0,str(NATIVE))
from geometry_statutory import CASES,open_drive
from engineering_statutory import parameters

FILES={'runner.py':'runner_statutory.py','geometry_base.py':'geometry_base.py',
       'geometry_statutory.py':'geometry_statutory.py','controller.py':'controller.py',
       'engineering.py':'engineering_statutory.py','cameras.py':'cameras.py',
       'measure_statutory.py':'measure_statutory.py','statutory_context.py':'statutory_context.py',
       'finalize.py':'finalize_statutory.py'}
TESTS=('test_runner.py','test_bundle_engineering.py','test_bundle_statutory_context.py')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def description():
    names=('drv.approaching','drv.in_intersection','st.intersection','st.railway_crossing',
           'st.centre_line','rel.occupies','kin.position','rel.centre_distance',
           'st.one_way_roadway','native_body_pose_control','camera_frame_join')
    return {'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':'Original Native map/road asset, full body and synchronized video; statutory_context source join',
        'time_window':'original 24 s / 480 frame attempt',
        'reference_frame':'surveyed Native map and original frame',
        'uncertainty':'50 ms samples; original physical map/pixels remain unobserved'} for name in names],
        'context_inputs':[{'name':'surveyed_statutory_approach','unit':'structured',
            'method':'Native OpenDRIVE railroad object and one-way lane direction readback'}],
        'limitations':['CPU construction and synthetic fixtures do not establish physical behavior or legal exception']}

def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    runtime_manifest=sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    shared=[{'path':dest,'content':(NATIVE/src).read_text()} for dest,src in FILES.items()]
    shared +=[{'path':'tests/'+name,'content':(NATIVE/name).read_text()} for name in TESTS]
    recording=description()
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':HERE.name,'runtime_manifest_sha256':runtime_manifest,
        'status':'draft_not_selected','scope':'railroad and one-way statutory source alternatives; no legal verdict',
        'cases':[]}
    proposals=[]
    for suffix,spec in CASES.items():
        case_id=HERE.name+'__'+suffix
        entry={'case_id':case_id,'kind':'draft_not_selected',
            'candidate_risk':{'status':'physical','reason':'Native railroad object/one-way lane readback, route realization and original video require physical review'},
            'measurement_contract':f'draft-statutory-contracts/{suffix}/measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c110454-saved-analysis-v1'},
            'candidates':[]}
        if (HERE/f'update015-{suffix}-recipe.json').is_file():
            entry['fixture_recipe']=f'work/{HERE.name}/update015-{suffix}-recipe.json'
        proposals.append({'case_id':case_id,'target_law_id':'NRS-484B-213-2b','target_type':'attempt',
            'recording_description':recording})
        requirements=[{'disposition_index':0,'requirement':'text-0',
                'source':'inputs/coverage/branch-sources.json','output_key':'left_side_driving',
                'method':'measure_left_side','value_type':'boolean','kind':'measured',
                'inputs':['native_samples.jsonl','road_geometry.json','statutory_context.json']},
                {'disposition_index':1,'requirement':'text-1',
                'source':'inputs/coverage/branch-sources.json','output_key':'statutory_approach_relation',
                'method':'measure_approach','value_type':'object','kind':'measured',
                'inputs':['native_samples.jsonl','road_geometry.json','statutory_context.json']}]
        if suffix.startswith('oneway_'):
            requirements.append({'disposition_index':2,'requirement':'text-2',
                'source':'inputs/coverage/branch-sources.json','output_key':'statutory_context',
                'method':'measure_context','value_type':'object','kind':'sourced_context',
                'inputs':['statutory_context.json','road_geometry.json']})
        write(HERE/'draft-statutory-contracts'/suffix/'measurement-contract.json',{
            'format':'worker-measurement-contract','case_id':case_id,
            'requirements':requirements,
            'negative':{'remove':['statutory_context.json'],
                'error_contains':'Missing required source: statutory_context.json'},
            'scope':'saved source identity and sampled geometry only; one-way exception applicability requires independent review'})
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            plan=parameters(suffix,candidate)
            config={'case_id':case_id,'selected_case_id':case_id,
                'supported_case_ids':[case_id],'case':{'case_id':case_id},
                'case_suffix':suffix,'candidate_id':candidate,'cell_id':'C110454',
                'law_id':'NRS-484B-213-2b','actor':'motor_vehicle_driver',
                'duration_s':24,'rate_hz':20,
                'required_atoms':['st.centre_line','rel.occupies','kin.position',
                    'st.railway_crossing' if suffix.startswith('rail_') else 'st.one_way_roadway'],
                'source_packets':[],
                'mandatory_channels':[c['name'] for c in recording['channels']],
                'recording_description':recording,
                'cameras':[{'name':name,'width':width,'height':height} for name,width,height in
                    [('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]],
                'engineering_knobs':plan['knobs'],'status':'unselected_native_runner_prototype'}
            files=shared+[{'path':'road.xodr','content':open_drive(suffix)},
                {'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
            construction={'case_id':case_id,'cell_id':'C110454','law_id':'NRS-484B-213-2b',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'recording_description':recording,
                'measurement_plan':{'method':'saved original body versus railroad/intersection boundary and Native lane direction source',
                    'status':'unselected_cpu_proposal'},
                'statutory_source_control':{'zone':spec['zone'],'one_way':spec['one_way'],
                    'boundary_x_m':spec['boundary_x_m'],
                    'authored_road_source':'road.xodr'},
                'static_checks':['authored same-cell road, railroad object or two co-directional lane geometry',
                    'source-bound 480-frame statutory context','four-view 480-frame recording contract'],
                'termination_rules':['full 480 original frames','capture or restoration failure retained'],
                'mechanisms':['observed-pose route controller','railroad object or one-way Native map readback',
                    'four synchronized lossless cameras'],
                'status':'unselected_cpu_draft'}
            path=HERE/'draft-statutory-candidates'/suffix/candidate/'construction.json'
            write(path,construction)
            ref={'id':candidate,'construction':str(path.relative_to(HERE)),
                'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                trigger=plan['fallback_trigger']
                ref['trigger']=trigger|{'failure_condition':f"{trigger['metric']} {trigger['op']} {trigger['threshold']}"}
                base=parameters(suffix,'primary')['knobs']
                ref['changed_knobs']=[k for k,v in plan['knobs'].items() if v!=base[k]]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE/'draft-statutory-execution-manifest.json',manifest)
    source=HERE/'proposals/cases.json'
    existing=json.loads(source.read_text())
    ids={c['case_id'] for c in proposals}
    existing['cases']=[c for c in existing['cases'] if c['case_id'] not in ids]+proposals
    write(source,existing)
    print(json.dumps({'cases':len(manifest['cases']),'candidates':sum(1+len(c['candidates']) for c in manifest['cases'])}))

if __name__=='__main__':main()
