"""Materialize current unselected C111256 Native bundles and source contracts."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NATIVE=HERE/'native'
sys.path.insert(0,str(NATIVE))
from engineering import CASES,CANDIDATES,TRIGGERS,CHANGES,parameters
from cameras import camera_plan

SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py','controller.py':'controller.py',
         'engineering.py':'engineering.py','measure_walk.py':'measure_walk.py',
         'cameras.py':'cameras.py','finalize.py':'finalize.py',
         'official_walk_source_audit.py':'official_walk_source_audit.py',
         'physical_walk_audit.py':'physical_walk_audit.py',
         'tests/test_native.py':'test_native.py'}
CHANNELS=('dev.pedestrian_signal','st.crosswalk','ru.pedestrian','rel.occupies',
          'drv.yields_to','kin.velocity','native_body_pose_control','camera_frame_join')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    shared={target:(NATIVE/source).read_text() for target,source in SOURCES.items()}
    recording={'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
                'method':'Saved original Native bus, pedestrian, Walk device, map and frame source; authored intent separate',
                'time_window':'24 s / 480-frame attempt',
                'reference_frame':'surveyed Native map and original frame identity',
                'uncertainty':'50 ms sampling; official Walk pixels and governance require independent audit'}
               for name in CHANNELS],
               'context_inputs':[],
               'limitations':['CPU synthetic diagnostics do not establish official Walk or physical yielding']}
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':HERE.name,'status':'draft_not_selected',
              'runtime_manifest_sha256':sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
              'cases':[]}
    for suffix in CASES:
        case_id=HERE.name+'__'+suffix
        contract_path=HERE/'draft-candidates'/suffix/'measurement-contract.json'
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical',
                   'reason':'Bus stopping, pedestrian Walk display and original camera framing require Native/pixel source review'},
               'measurement_contract':str(contract_path.relative_to(HERE)),
               'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c111256-saved-analysis-v1'},
               'candidates':[]}
        recipe_path=HERE/f'update015-{suffix}-recipe.json'
        if recipe_path.is_file():entry['fixture_recipe']=str(recipe_path.relative_to(REPO))
        for candidate in CANDIDATES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=suffix,
                candidate_id=candidate,knobs=parameters(suffix,candidate)['knobs'],
                supported_case_ids=[case_id],case={'case_id':case_id},
                source_packets=[],recording_description=recording,
                cameras=[{'name':c['name'],'width':c['width'],'height':c['height']}
                         for c in camera_plan(candidate)])
            files=[{'path':name,'content':code} for name,code in shared.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C111256',
                'law_id':'NRS-484B-283-1d1','actor':'bus_driver',
                'entrypoint':'runner.py','files':files,'recording_description':recording,
                'mechanisms':['authored through bus lane and pedestrian-facing Walk device',
                    'source-fed bus hold controller and pedestrian crossing actor',
                    'four synchronized original source cameras and saved-only raw analysis'],
                'termination_rules':['exact 480 original frames',
                    'capture/restoration errors retained; original display remains Unknown until audit'],
                'status':'unselected_cpu_draft'}
            path=HERE/'draft-candidates'/suffix/candidate/'construction.json'
            write(path,construction)
            ref={'id':candidate,'construction':str(path.relative_to(HERE)),
                 'construction_sha256':sha(path)}
            if candidate=='primary':
                entry.update({key:ref[key] for key in ('construction','construction_sha256')})
            else:
                trigger=TRIGGERS[candidate]
                ref.update(trigger={'source':trigger['source'],'metric':trigger['metric'],
                                    'failure_condition':f"{trigger['op']} {trigger['threshold']}"},
                           changed_knobs=list(CHANGES[candidate]))
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE/'draft-execution-manifest.json',manifest)
    write(HERE/'proposals/cases.json',{
        'format':'worker-draft-proposals-v1','status':'draft_not_selected',
        'cases':[{'case_id':case['case_id'],'target_type':'attempt',
                  'recording_description':recording} for case in manifest['cases']]})
    return manifest

if __name__=='__main__':
    value=build()
    print(json.dumps({'cases':len(value['cases']),
        'candidate_bundles':sum(1+len(row['candidates']) for row in value['cases']),
        'selected':False}))
