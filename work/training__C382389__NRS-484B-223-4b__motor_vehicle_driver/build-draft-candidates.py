"""Build unselected exact-case CPU draft bundles; never marks delivery ready."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
ASSIGNMENT=FOLDER.name
RUNTIME_MANIFEST='391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'
NAMES=('primary','fallback1','fallback2','fallback3')
SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py','controller.py':'controller.py',
         'engineering.py':'engineering.py',
         'measure_crossing.py':'measure_crossing.py','finalize.py':'finalize.py','cameras.py':'cameras.py',
         'fallback_triggers.py':'fallback_triggers.py',
         'tests/test_measure_crossing.py':'test_measure_crossing.py',
         'tests/test_controller.py':'test_controller.py',
         'tests/test_candidate_knobs.py':'test_candidate_knobs.py',
         'tests/test_runner_survey.py':'test_runner_survey.py',
         'tests/test_fallback_triggers.py':'test_fallback_triggers.py',
         'tests/test_cameras.py':'test_cameras.py'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,object):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(object,indent=2)+'\n')


def description():
    names=('drv.in_intersection','st.intersection','st.turn_lane','rel.occupies',
           'kin.heading','native_body_pose_control','camera_frame_join')
    methods={
      'drv.in_intersection':'Original full body crossing the intersection boundary with Native road/lane identity',
      'st.intersection':'Native map readback and original body/intersection boundary history',
      'st.turn_lane':'Native lane ID and authored right-only cue; design confirmation pending',
      'rel.occupies':'Full original Native body footprint across adjacent and right-only lane candidates',
      'kin.heading':'Original Native straight heading across approach, connector and complete exit',
      'native_body_pose_control':'Original Native pose, velocity, applied control and body footprint',
      'camera_frame_join':'Every source camera frame joined to original Native frame and timestamp'}
    return {'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':methods[name],'time_window':'entire original 24 s / 480 frame attempt',
        'reference_frame':'surveyed Native map and original frame, with authored intent separate',
        'uncertainty':'50 ms sampling and map/body precision; no statutory threshold inferred'} for name in names],
        'context_inputs':[{'name':'surveyed_right_turn_lane_intersection','unit':'structured',
        'method':'Native map/lane readback hash, right-only design cue and intersection-boundary source'}],
        'limitations':['Right-only lane designation, actual route tracking, map lane links, camera pixels and physical success require Native evidence',
                       'Finite samples do not prove intersample behavior or legal outcome']}


def build():
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':RUNTIME_MANIFEST,
              'status':'draft_not_selected','cases':[]}
    shared={name:(NATIVE/source).read_text() for name,source in SOURCES.items()}
    recording=description()
    for suffix in ('reference','contrast'):
        case_id=ASSIGNMENT+'__'+suffix
        contract_path=FOLDER/'draft-candidates'/suffix/'measurement-contract.json'
        write(contract_path,{'format':'worker-measurement-contract-v1','case_id':case_id,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-223-4b',
                'source':'NRS 484B.223(4)(b)','output_key':'right_only_lane_through_crossing',
                'method':'measure_right_only_lane_crossing','value_type':'object','kind':'measured',
                'inputs':['native_samples.jsonl','road_geometry.json']}],
            'negative':{'remove':['native_samples.jsonl'],
                'error_contains':'Missing required source: native_samples.jsonl'}})
        entry={'case_id':case_id,'kind':'draft_not_selected','candidate_risk':{
            'status':'physical','reason':'Right-only lane designation, continuous crossing, tracking and camera framing require original Native evidence'},
            'measurement_contract':str(contract_path.relative_to(FOLDER)),
            'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c382389-right-only-lane-crossing-saved-analysis-v1'},
            'candidates':[]}
        for candidate in NAMES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=suffix,
                          candidate_id=candidate,supported_case_ids=[case_id],
                          case={'case_id':case_id},
                          recording_description=recording,
                          cameras=[{'name':n,'width':w,'height':h,
                            'pose_strategy':'candidate-specific declared Native mount; see cameras.py',
                            'fov_deg':'90 primary / 105 framing fallback where applicable'}
                            for n,w,h in [('overview',1920,1080),('approach',1280,720),
                                           ('reference_corner',1280,720),('driver_reference',1280,720)]])
            files=[{'path':name,'content':code} for name,code in shared.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C382389','law_id':'NRS-484B-223-4b',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'measurement_plan':{'method':'saved Native full-body and lane-ID straight crossing of the intersection; see measure_crossing.py',
                    'status':'prototype_not_runtime_compatible'},
                'recording_description':recording,
                'static_checks':['authored map links','route continuity','prospective body pavement containment',
                                 'pinned Core atom preflight','CPU controller/measurement/camera tests'],
                'termination_rules':['full 480 original frames','failure retained on capture or restoration error'],
                'mechanisms':['two straight junction lanes with authored right-only cue',
                              'observed-pose path controller','four synchronized lossless cameras'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=FOLDER/relative
            write(path,construction)
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                risk={
                    'fallback1':('straight connector clearance or complete exit','Native route lacks requested straight connector or full-body exit absent by 24 s','straight route start -50 m to -55 m'),
                    'fallback2':('straight path tracking','maximum recorded route error on x=-10..7 m exceeds 0.35 m','pure-pursuit lookahead 4.0 m to 3.0 m'),
                    'fallback3':('right-only-lane camera framing','independent pixel audit cannot see full body and right-only lane cue in 95% of approach frames','ego-following camera height 3.2 m to 4.5 m and FOV 90 to 105 degrees')
                }[candidate]
                ref.update(trigger={'source':'source-hashed original Native samples, surveyed geometry, reviewed lane-link and pixel audits',
                                    'evaluator':'fallback_triggers.py:evaluate','metric':risk[0],
                                    'failure_condition':risk[1]},changed_knobs=[risk[2]])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    value=build();print(json.dumps({'cases':len(value['cases']),
      'candidates':sum(1+len(c['candidates']) for c in value['cases']),
      'status':value['status']}))
