"""Materialize exact unselected C102372 Native construction bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NATIVE=HERE/'native'
sys.path.insert(0,str(NATIVE))
from engineering import CANDIDATES,CHANGES,TRIGGERS
from passing_engineering import CHANGES as PASSING_CHANGES,TRIGGERS as PASSING_TRIGGERS
from passing_hold_engineering import CHANGES as HOLD_CHANGES,TRIGGERS as HOLD_TRIGGERS
from conditions_engineering import CHANGES as CONDITIONS_CHANGES,TRIGGERS as CONDITIONS_TRIGGERS
from runner import cameras,plan_for

SOURCES=('runner.py','engineering.py','geometry.py','measure_gap.py',
         'trigger_measure.py','finalize.py','two_lane_engineering.py',
         'two_lane_exception.py','passing_carveout.py','passing_engineering.py',
         'passing_trigger.py','passing_hold_engineering.py','passing_hold_trigger.py',
         'conditions_qualifier.py','conditions_engineering.py','conditions_trigger.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def recording(suffix):
    methods={
        'ego_body_pose':('structured','Original Native 80-inch truck body/pose/lane/velocity'),
        'lead_body_pose':('structured','Separate original Native lead truck body/pose/lane/velocity'),
        'surface_gap_m':('m','Original full-body bumper gap sampled before speed request'),
        'camera_frame_join':('structured','Original four-view video to Native frame join')}
    if suffix in ('passing_overtake','passing_hold'):
        methods.pop('surface_gap_m')
        methods['body_clearance_m']=('m','Original truck-body clearance in the passing sequence')
    return {'channels':[{'name':name,'unit':unit,'sampling_rate_hz':20,
        'method':method,'time_window':'full original 24 s / 480-frame attempt',
        'reference_frame':'Native hill-crest road, actor body and original frame',
        'uncertainty':'50 ms sampling; physical conditions and pixels require later review'}
        for name,(unit,method) in methods.items()],
        'context_inputs':[{'name':'conditions_permit','unit':'structured',
            'method':'original conditions review required; synthetic assertion is diagnostic'}],
        'limitations':['Road-arc gap is a measurement, not a legal verdict',
            'Original truck classification, conditions and camera pixels need physical review']}


def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    draft_cases=[case for case in plan['cases'] if case['case_id'].rsplit('__',1)[-1]
                 in ('probe_1','probe_2','two_lane_exception','passing_overtake',
                     'passing_hold','conditions_steady','conditions_lead_brake')]
    if [case['case_id'].rsplit('__',1)[-1] for case in draft_cases]!=[
            'probe_1','probe_2','two_lane_exception','passing_hold','passing_overtake',
            'conditions_steady','conditions_lead_brake']:
        raise ValueError('Exact C102372 draft case set differs')
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':HERE.name,'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
        'status':'draft_not_selected','cases':[]}
    proposal={'format':'worker-draft-proposals-v1','cases':[]}
    common=[{'path':name,'content':(NATIVE/name).read_text()} for name in SOURCES]
    common.append({'path':'tests/test_native.py','content':(NATIVE/'test_native.py').read_text()})
    common.append({'path':'tests/test_two_lane_native.py',
                   'content':(NATIVE/'test_two_lane_native.py').read_text()})
    common.append({'path':'tests/test_passing_native.py',
                   'content':(NATIVE/'test_passing_native.py').read_text()})
    common.append({'path':'tests/test_passing_hold_native.py',
                   'content':(NATIVE/'test_passing_hold_native.py').read_text()})
    common.append({'path':'tests/test_conditions_native.py',
                   'content':(NATIVE/'test_conditions_native.py').read_text()})
    for case in draft_cases:
        case_id=case['case_id'];suffix=case_id.rsplit('__',1)[-1]
        description=recording(suffix)
        contract=NATIVE/('measurement-contract-'+suffix+'.json')
        if json.loads(contract.read_text())['case_id']!=case_id:
            raise ValueError('Exact case measurement contract differs')
        entry={'case_id':case_id,'kind':'draft_not_selected',
            'measurement_contract':str(contract.relative_to(HERE)),
            'measurement_procedure':{'entrypoint':'finalize.py',
                                     'output_schema':'c102372-saved-analysis-v1'},
            'candidate_risk':{'status':'physical',
                'reason':'Original truck width, 480-frame control, road readback, camera and conditions unobserved'},
            'candidates':[]}
        proposal['cases'].append({'case_id':case_id,'target_type':case['target_type'],
                                  'recording_description':description})
        for candidate in CANDIDATES:
            knobs=plan_for(suffix,candidate)['knobs']
            config={'case_id':case_id,'selected_case_id':case_id,
                'supported_case_ids':[case_id],'case_suffix':suffix,
                'candidate_id':candidate,'law_id':'NRS-484B-127-2',
                'cell_id':'C102372','actor':'heavy_vehicle_driver',
                'rate_hz':20,'duration_s':24,'case':{'case_id':case_id},
                'knobs':knobs,'cameras':[{key:camera[key] for key in
                    ('name','width','height')} for camera in cameras(candidate)],
                'required_atoms':['ru.truck','st.lane','rel.surface_gap',
                                  'rel.ahead_behind_in_lane'],
                'recording_description':description,'source_packets':[],
                'status':'unselected_native_draft'}
            files=common+[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
            construction={'case_id':case_id,'law_id':'NRS-484B-127-2',
                'cell_id':'C102372','actor':'heavy_vehicle_driver',
                'entrypoint':'runner.py','files':files,
                'recording_description':description,
                'measurement_plan':{'method':'Original full-body truck road-arc gap, width and lane context',
                    'status':'source_bound_cpu_draft'},
                'static_checks':['authored hill-crest and directional lanes',
                    'two 80-inch Native truck body readbacks','480-frame joined four-view capture',
                    'three distinct fallback control and camera knobs'],
                'termination_rules':['480 original 20 Hz frames',
                    'retain failed capture/restoration report'],
                'mechanisms':['same-cell hill-crest truck following',
                    'source-bound body width and road-arc gap','four original camera views'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=HERE/relative;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2)+'\n')
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                trigger=(PASSING_TRIGGERS if suffix=='passing_overtake' else
                         HOLD_TRIGGERS if suffix=='passing_hold' else
                         CONDITIONS_TRIGGERS[suffix] if suffix in CONDITIONS_TRIGGERS else
                         TRIGGERS)[candidate]
                ref.update(trigger={'source':trigger['source'],'metric':trigger['metric'],
                    'failure_condition':f"{trigger['metric']} {trigger['op']} {trigger['threshold']}"},
                    changed_knobs=list((PASSING_CHANGES if suffix=='passing_overtake' else
                                        HOLD_CHANGES if suffix=='passing_hold' else
                                        CONDITIONS_CHANGES[suffix] if suffix in CONDITIONS_CHANGES else
                                        CHANGES)[candidate]))
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (HERE/'proposals').mkdir(exist_ok=True)
    (HERE/'proposals/cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
    return {'cases':len(manifest['cases']),'unselected_bundles':sum(
        1+len(entry['candidates']) for entry in manifest['cases'])}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
