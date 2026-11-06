"""Materialize exact unselected C10316 Native proposal bundles for pinned offline."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NATIVE=HERE/'native'
NAMES=('primary','fallback1','fallback2','fallback3')
SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py',
         'engineering.py':'engineering.py','measure_crosswalk.py':'measure_crosswalk.py',
         'finalize.py':'finalize.py',
         'road.xodr':'road.xodr','tests/test_offline.py':'test_offline.py'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recording():
    channels=[]
    for name,unit,method in (
        ('kin.position','m','Original Native pedestrian center and footprint'),
        ('kin.heading','unit vector','Original Native pedestrian transform forward'),
        ('rel.occupies','structured','Original footprint and named crosswalk geometry'),
        ('native_pedestrian_pose','structured','Original body, pose, heading and velocity'),
        ('camera_frame_join','structured','Four camera frames joined to Native frame/time')):
        channels.append({'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,
                         'time_window':'entire original 12 s / 240-frame attempt',
                         'reference_frame':'Native map and pedestrian/crosswalk coordinates',
                         'uncertainty':'50 ms frame interval; Native footprint and pixel audit required'})
    return {'channels':channels,'context_inputs':[{'name':'practicability_facts',
             'unit':'structured','method':'Original Native obstruction and pedestrian inventory plus independent review'}],
            'limitations':['Right-half count is descriptive, not a practicability verdict',
                           'Authored OpenDRIVE crosswalk is not proof of Native crosswalk inventory',
                           'Source camera pixels and pedestrian physics require independent saved audit']}


def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    common={name:(NATIVE/source).read_text() for name,source in SOURCES.items()}
    description=recording()
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':HERE.name,'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
              'status':'draft_not_selected','cases':[]}
    for case in plan['cases']:
        case_id=case['case_id']; suffix=case_id.rsplit('__',1)[-1]
        contract=HERE/'draft-crosswalk'/suffix/'measurement-contract.json'
        if json.loads(contract.read_text())['case_id']!=case_id:
            raise ValueError('Case measurement contract differs')
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical','reason':'Native walker path, crosswalk inventory, camera framing and practicability facts remain unverified'},
               'measurement_contract':str(contract.relative_to(HERE)),
               'measurement_procedure':{'entrypoint':'finalize.py',
                                        'output_schema':'c10316-saved-crosswalk-analysis-v1'},
               'candidates':[]}
        for ident in NAMES:
            source_plan=json.loads((HERE/'draft-candidates'/suffix/ident/'construction.json').read_text())
            config={'case_id':case_id,'selected_case_id':case_id,'case_suffix':suffix,
                    'candidate_id':ident,'case':{'case_id':case_id},
                    'cell_id':'C10316','law_id':'NRS-484B-293','actor':'pedestrian',
                    'duration_s':12,'rate_hz':20,
                    'required_atoms':['ru.pedestrian','kin.position','kin.heading','st.crosswalk','rel.occupies'],
                    'source_packets':[],
                    'cameras':[{'name':name,'width':width,'height':height} for name,width,height in (
                        ('overview',1920,1080),('approach',1280,720),
                        ('reference_corner',1280,720),('pedestrian_reference',1280,720))],
                    'recording_description':description,'status':'unselected_native_runner_proposal'}
            files=[{'path':name,'content':content} for name,content in common.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C10316','law_id':'NRS-484B-293',
                          'actor':'pedestrian','entrypoint':'runner.py','files':files,
                          'recording_description':description,
                          'measurement_plan':{'method':'Original footprint-based crosswalk-half counts',
                                              'status':'prototype_not_runtime_compatible'},
                          'static_checks':['authored OpenDRIVE alley and crosswalk geometry',
                                           'four-view camera profile','source-bound original pedestrian footprint'],
                          'termination_rules':['240 original 20 Hz frames',
                                               'retain failed attempt on capture or restoration error'],
                          'mechanisms':['same-cell marked alley crosswalk','moving Native pedestrian',
                                        'direction-relative right/left footprint measurement',
                                        'four synchronized lossless cameras'],
                          'status':'unselected_cpu_draft'}
            path=HERE/'draft-bundles'/suffix/ident/'construction.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2)+'\n')
            ref={'id':ident,'construction':str(path.relative_to(HERE)),
                 'construction_sha256':sha(path)}
            if ident=='primary':entry.update(ref)
            else:
                rule=source_plan['engineering']['trigger']
                ref.update(trigger={'source':rule['source'],'metric':rule['kind'],
                                    'failure_condition':str(rule['kind'])+' '+str(rule['threshold'])},
                           changed_knobs=[{
                               'fallback1':'spawn start -4 to -6 m and 3 s pre-roll',
                               'fallback2':'controller lookahead 0.5 to 0.25 s',
                               'fallback3':'overhead camera 6 to 9 m'}[ident]])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':len(manifest['cases']),
                      'unselected_exact_bundles':sum(1+len(x['candidates']) for x in manifest['cases']),
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']},sort_keys=True))


if __name__=='__main__':build()
