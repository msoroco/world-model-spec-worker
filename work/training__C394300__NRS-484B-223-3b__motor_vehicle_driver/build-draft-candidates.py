"""Materialize exact, unselected center-turn-lane CPU draft bundles."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
ASSIGNMENT=FOLDER.name
RUNTIME_MANIFEST='391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'
SUFFIXES=('witness_1','witness_2','numeric_1_0','numeric_1_1','numeric_1_2')
NAMES=('primary','fallback1','fallback2','fallback3')
SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py','controller.py':'controller.py',
         'engineering.py':'engineering.py','measure_center_lane.py':'measure_center_lane.py',
         'measure_saved.py':'measure_saved.py','finalize.py':'finalize.py',
         'fallback_triggers.py':'fallback_triggers.py',
         'cameras.py':'cameras.py',
         'tests/test_measure_center_lane.py':'test_measure_center_lane.py',
         'tests/test_controller.py':'test_controller.py',
         'tests/test_candidate_knobs.py':'test_candidate_knobs.py',
         'tests/test_fallback_triggers.py':'test_fallback_triggers.py',
         'tests/test_cameras.py':'test_cameras.py'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def description():
    methods={
      'st.turn_lane':'Native lane identity and source-backed designation of one bidirectional center lane reserved for turns',
      'rel.occupies':'Original body polygon and same-frame Native lane membership',
      'drv.turning':'Original heading and yaw-rate turn onset bracket before the left turn',
      'kin.heading':'Original pose heading at each frame',
      'st.intersection':'Native junction and road/lane readback at approach and turn',
      'native_body_pose_control':'Original Native pose, velocity, control and ordered footprint',
      'camera_frame_join':'Every source camera frame joined to Native frame and timestamp'}
    return {'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
        'method':method,'time_window':'entire original 24 s / 480 frame attempt',
        'reference_frame':'surveyed Native map and original frame',
        'uncertainty':'50 ms event brackets and map/body precision; threshold classification may remain unresolved'}
        for name,method in methods.items()],
        'context_inputs':[{'name':'surveyed_center_turn_lane','unit':'structured',
            'method':'Native road/lane and design-source readback for bidirectional turn-only designation'}],
        'limitations':['Authored lane type alone does not prove bidirectional turn-only design in Native',
            'Commanded 180/199/200/201/220 ft probes are not measured distances or legal outcomes',
            'Map links, physical route tracking and original camera pixels remain unverified']}


def build():
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':RUNTIME_MANIFEST,
        'status':'draft_not_selected','cases':[]}
    shared={name:(NATIVE/source).read_text() for name,source in SOURCES.items()}
    recording=description()
    for suffix in SUFFIXES:
        case_id=ASSIGNMENT+'__'+suffix
        contract_path=FOLDER/'draft-measurements'/(suffix+'-contract.json')
        contract=json.loads(contract_path.read_text())
        assert contract['case_id']==case_id
        entry={'case_id':case_id,'kind':'draft_not_selected','candidate_risk':{
            'status':'physical','reason':'Native center-lane designation, observed distance, lane-change tracking and camera framing require original capture'},
            'measurement_contract':str(contract_path.relative_to(FOLDER)),
            'measurement_procedure':{'entrypoint':'finalize.py',
                'output_schema':'c394300-3b-saved-distance-analysis-v1'},'candidates':[]}
        for candidate in NAMES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=suffix,
                candidate_id=candidate,supported_case_ids=[case_id],case={'case_id':case_id},
                recording_description=recording,
                cameras=[{'name':n,'width':w,'height':h,
                    'pose_strategy':'candidate-specific declared Native mount; see cameras.py',
                    'fov_deg':'90 primary / 105 framing fallback where applicable'}
                    for n,w,h in [('overview',1920,1080),('approach',1280,720),
                                  ('reference_corner',1280,720),('driver_reference',1280,720)]])
            files=[{'path':name,'content':code} for name,code in shared.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C394300','law_id':'NRS-484B-223-3b',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'measurement_plan':{'method':'saved Native body/lane entry-to-left-turn path-distance interval; see measure_center_lane.py',
                    'status':'prototype_not_runtime_compatible'},'recording_description':recording,
                'static_checks':['authored map links','route continuity','prospective body pavement containment',
                    'CPU controller, measurement and camera tests'],
                'termination_rules':['full 480 original frames','failure retained on capture or restoration error'],
                'mechanisms':['same-cell center-lane authored map and five distance requests',
                    'observed-pose path controller','four synchronized lossless cameras'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=FOLDER/relative;write(path,construction)
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(ref)
            else:
                risk={
                    'fallback1':('initial through-lane placement and lane-change convergence',
                        'Native initial body is outside the through lane or center-lane entry is not attained by 3 s',
                        'route start x -95 m to -98 m'),
                    'fallback2':('approach and turn path tracking',
                        'maximum original Native route error near lane change or turn exceeds 0.35 m',
                        'pure-pursuit lookahead 4 m to 3 m'),
                    'fallback3':('center-lane marking and body camera visibility',
                        'independent pixel audit cannot see marking and body in at least 95% of approach frames',
                        'ego-following mount height 3.2 m to 4.5 m and FOV 90 to 105 degrees')
                }[candidate]
                ref.update(trigger={'source':'original Native frame record and saved source pixels',
                    'metric':risk[0],'failure_condition':risk[1]},changed_knobs=[risk[2]])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    return manifest


if __name__=='__main__':
    value=build();print(json.dumps({'cases':len(value['cases']),
        'candidates':sum(1+len(c['candidates']) for c in value['cases']),
        'status':value['status']}))
