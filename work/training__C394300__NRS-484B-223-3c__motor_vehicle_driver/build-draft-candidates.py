"""Materialize twelve exact, unselected after-left-turn CPU construction bundles."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
NATIVE=FOLDER/'native'
ASSIGNMENT=FOLDER.name
SUFFIXES=('below_50_ft','at_50_ft','above_50_ft')
NAMES=('primary','fallback1','fallback2','fallback3')
SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py','controller.py':'controller.py',
         'engineering.py':'engineering.py','measure_after_turn.py':'measure_after_turn.py',
         'finalize.py':'finalize.py','cameras.py':'cameras.py',
         'trigger_evidence.py':'trigger_evidence.py',
         'tests/test_measure_after_turn.py':'test_measure_after_turn.py',
         'tests/test_candidate_knobs.py':'test_candidate_knobs.py',
         'tests/test_trigger_evidence.py':'test_trigger_evidence.py'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def recording():
    methods={
      'st.centre_turn_lane':'Native road/lane survey and original body membership; design designation awaits independent proof',
      'drv.turning':'Original heading and connector-to-highway road transition',
      'kin.path_length':'Original Native pose samples and sampled event path interval',
      'drv.lane_change':'Original body contact with through lane and eventual full-body merge',
      'rel.occupies':'Ordered original Native body polygon and lane identity',
      'native_body_pose_control':'Original Native pose, velocity, controller request and footprint',
      'camera_frame_join':'Each source camera frame joined to original Native frame and time'}
    return {'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':method,'time_window':'entire original 24 s / 480 frame attempt',
        'reference_frame':'surveyed Native map and original frame',
        'uncertainty':'50 ms event brackets and map/body precision; 50-foot threshold may remain unresolved'}
        for name,method in methods.items()],
        'context_inputs':[{'name':'surveyed_center_turn_lane','unit':'structured',
            'method':'Native road/lane/design-source readback for bidirectional turn-only designation'}],
        'limitations':['Authored lane type does not prove Native bidirectional turn-only design',
            'Commanded 45/50/55 ft merge stations are not measured distances or legal outcomes',
            'Map links, physical route tracking and original camera pixels remain unverified']}


def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
      'assignment_id':ASSIGNMENT,
      'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
      'status':'draft_not_selected','cases':[]}
    shared={name:(NATIVE/source).read_text() for name,source in SOURCES.items()}
    captured=recording()
    for suffix in SUFFIXES:
        case_id=ASSIGNMENT+'__'+suffix
        contract_path=FOLDER/'draft-measurements'/(suffix+'-contract.json')
        contract=json.loads(contract_path.read_text())
        if contract['case_id']!=case_id:raise ValueError('Case-specific measurement contract differs')
        entry={'case_id':case_id,'kind':'draft_not_selected',
          'candidate_risk':{'status':'physical','reason':'Native center-lane designation, connector/merge tracking, observed distance and camera framing require original capture'},
          'measurement_contract':str(contract_path.relative_to(FOLDER)),
          'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c394300-3c-saved-after-turn-analysis-v1'},
          'candidates':[]}
        for candidate in NAMES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=suffix,
                candidate_id=candidate,supported_case_ids=[case_id],case={'case_id':case_id},
                recording_description=captured,
                cameras=[{'name':n,'width':w,'height':h,
                    'pose_strategy':'candidate-specific declared Native mount; see cameras.py',
                    'fov_deg':'90 primary / 105 visibility fallback where applicable'}
                    for n,w,h in [('overview',1920,1080),('approach',1280,720),
                                  ('reference_corner',1280,720),('driver_reference',1280,720)]])
            files=[{'path':name,'content':code} for name,code in shared.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C394300','law_id':'NRS-484B-223-3c',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'measurement_plan':{'method':'saved Native left-turn completion-to-merge-onset path-distance interval; see measure_after_turn.py',
                                    'status':'prototype_not_runtime_compatible'},
                'recording_description':captured,
                'static_checks':['authored map links','route continuity','prospective body pavement containment',
                                 'CPU controller, measurement and camera tests'],
                'termination_rules':['full 480 original frames','failure retained on capture or restoration error'],
                'mechanisms':['same-cell inbound-to-center-lane left turn and three merge-station requests',
                              'observed-pose path controller','four synchronized lossless cameras'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=FOLDER/relative;write(path,construction)
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                risks={'fallback1':('original Native body and turn-completion samples',
                                    'inbound_body_containment_fraction and turn_completion_time_s',
                                    'containment fraction < 1.0 or turn completion > 4.0 s',
                                    'inbound route start 45 m to 42 m'),
                       'fallback2':('original Native route-error samples',
                                    'max_premerge_route_error_m',
                                    'maximum route error > 0.35 m',
                                    'pure-pursuit lookahead 4 m to 3 m'),
                       'fallback3':('independent original-pixel visibility audit',
                                    'marking_and_body_visible_fraction',
                                    'visibility fraction < 0.95',
                                    'approach/reference FOV 90 to 105 degrees and mount height 3.2 m to 4.5 m')}
                source,metric,condition,changed=risks[candidate]
                ref.update(trigger={'source':source,'metric':metric,'failure_condition':condition},
                           changed_knobs=[changed])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    value=build();print(json.dumps({'cases':len(value['cases']),
        'candidates':sum(1+len(c['candidates']) for c in value['cases']),
        'status':value['status']}))
