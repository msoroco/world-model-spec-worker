"""Materialize eight exact unselected 3(a) CPU runner bundles."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
NATIVE=FOLDER/'native'
ASSIGNMENT=FOLDER.name
CASES=('controlled_1','controlled_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
SOURCES={name:name for name in ('runner.py','geometry.py','controller.py','engineering.py',
                                'cameras.py','survey.py','measure_saved.py','finalize.py',
                                'trigger_evidence.py')}
SOURCES['tests/test_constructions.py']='test_constructions.py'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    policies=json.loads((FOLDER/'draft-construction/candidate-manifest.json').read_text())
    assert policies['assignment_id']==ASSIGNMENT
    code={target:(NATIVE/source).read_text() for target,source in SOURCES.items()}
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ASSIGNMENT,
              'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
              'status':'draft_not_selected','cases':[]}
    for case in CASES:
        case_id=ASSIGNMENT+'__'+case
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'measurement_contract':f'draft-measurements/{case}-contract.json',
               'measurement_procedure':{'entrypoint':'finalize.py',
                                        'output_schema':'c394300-3a-saved-analysis-v1'},
               'candidate_risk':{'status':'physical',
                  'reason':'Native center-lane design, movement, original pixels and purpose require saved review'},
               'candidates':[]}
        for candidate in CANDIDATES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=case,
                          candidate_id=candidate,supported_case_ids=[case_id],
                          case={'case_id':case_id},
                          recording_description={'channels':[
                              {'name':name,'unit':'structured','sampling_rate_hz':20,
                               'method':'Original Native frame/body/lane survey and controlled route; see runner.py',
                               'time_window':'entire 24 s / 480 frame attempt',
                               'reference_frame':'surveyed Native map and original frame',
                               'uncertainty':'50 ms frame bracket; physical purpose unverified'}
                              for name in config['mandatory_channels']],
                              'limitations':['Authored purpose is not observed driver intent',
                                             'CPU synthetic rows are not physical observations']},
                          cameras=[{'name':name,'width':width,'height':height,
                                    'pose_strategy':'candidate-specific cameras.py'}
                                   for name,width,height in [('overview',1920,1080),
                                     ('approach',1280,720),('reference_corner',1280,720),
                                     ('driver_reference',1280,720)]])
            files=[{'path':name,'content':content} for name,content in code.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C394300','law_id':'NRS-484B-223-3a',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'measurement_plan':{'method':'saved Native body/lane path and separate source-declared purpose',
                                    'status':'prototype_not_runtime_compatible'},
                'recording_description':config['recording_description'],
                'static_checks':['authored OpenDRIVE links and route continuity',
                                 'CPU body/source processor and candidate tests'],
                'termination_rules':['full 480 original frames',
                                     'failure retained on capture or restoration error'],
                'mechanisms':['same frozen-cell two-opportunity controlled pair',
                              'observed-pose path controller','four synchronized lossless cameras'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{case}/{candidate}/construction.json'
            target=FOLDER/relative;write(target,construction)
            ref={'id':candidate,'construction':relative,'construction_sha256':sha(target)}
            if candidate=='primary':entry.update(ref)
            else:
                policy=next(row for row in policies['cases'] if
                            row['case_id']==case_id and row['candidate_id']==candidate)
                ref['trigger']=policy['trigger']
                ref['changed_knobs']={'fallback1':['route_start_x_m','entry_advance_m'],
                                      'fallback2':['controller_knobs'],
                                      'fallback3':['camera_plan']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    return {'cases':len(manifest['cases']),'candidate_bundles':len(CASES)*len(CANDIDATES),
            'manifest_sha256':sha(FOLDER/'draft-execution-manifest.json'),
            'status':manifest['status'],'ready_claimed':False}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
