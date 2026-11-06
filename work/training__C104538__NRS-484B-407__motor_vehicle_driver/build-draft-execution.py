"""Build source-exact, unselected C104538 Native CPU constructions."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
ASSIGNMENT=FOLDER.name
SUFFIXES=('below_500_ft','at_500_ft','above_500_ft')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
MODULES=('runner.py','engineering.py','geometry.py','obstruction.py','cameras.py','sightline.py','measure_native.py','finalize.py')
TESTS=('test_runner.py','test_engineering.py','test_sightline.py','test_obstruction.py','test_measure_native.py','test_finalize.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build():
    runtime_proof=json.loads((FOLDER.parents[1]/'work/_shared/runtime-proof.json').read_text())
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ASSIGNMENT,'status':'draft_not_selected',
              'runtime_manifest_sha256':runtime_proof['runtime_manifest_sha256'],'cases':[]}
    common=[{'path':name,'content':(NATIVE/name).read_text()} for name in MODULES]
    common += [{'path':'tests/'+name,'content':(NATIVE/name).read_text()} for name in TESTS]
    for suffix in SUFFIXES:
        case_id=ASSIGNMENT+'__'+suffix
        source=FOLDER/'draft-sightline'/suffix
        sources=[{'path':'authored_road.xodr','content':(source/'road.xodr').read_text()}]
        sources += [{'path':name,'content':(source/name).read_text()}
                    for name in ('obstruction.json','measurement.json')]
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical',
                 'reason':'Native crest, obstruction geometry, physical opacity, driver-eye pixels and turn completion remain unmeasured'},
               'measurement_procedure':{'entrypoint':'finalize.py',
                  'output_schema':'c104538-saved-analysis-v1'},
               'candidates':[]}
        for candidate in CANDIDATES:
            plan=json.loads((FOLDER/'draft-candidates'/suffix/candidate/'plan.json').read_text())
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,
                          supported_case_ids=[case_id],case={'case_id':case_id},
                          case_suffix=suffix,candidate_id=candidate,
                          source_packets=[],
                          cameras=[{'name':name,'width':width,'height':height}
                             for name,width,height in (('overview',1920,1080),
                                 ('reference_left',1280,720),('reference_right',1280,720),('ego',1280,720))])
            description={'channels':[{'name':name,'unit':'structured',
                'sampling_rate_hz':20,'method':'original Native actor/map/channel source',
                'time_window':'entire original 24 s / 480-frame attempt',
                'reference_frame':'original Native frame and map readback',
                'uncertainty':'physical visibility and pixels require independent audit'}
                for name in ('drv.u_turn','st.curvature','st.grade','st.crest',
                    'st.sight_distance','rel.oncoming','drv.approaching','kin.position')],
                'context_inputs':[],
                'limitations':['Physical and legal conditions require original Native measurement and independent pixel audit']}
            config['recording_description']=description
            files=common+sources+[
                {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                {'path':'construction-plan.json','content':json.dumps(plan,indent=2)+'\n'}]
            construction={'case_id':case_id,'cell_id':'C104538','law_id':'NRS-484B-407',
                'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
                'recording_description':description,
                'mechanisms':['authored curved crest OpenDRIVE','Native obstruction actor chain',
                              'two approaching reference actors','four lossless original views'],
                'termination_rules':['480 frames or retained failure','world restoration'],
                'status':'unselected_cpu_draft'}
            relative=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=FOLDER/relative
            write(path,construction)
            reference={'id':candidate,'construction':relative,
                       'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(reference)
            else:
                trigger=plan['retry_trigger']
                reference.update(trigger={'source':trigger['source'],
                    'metric':trigger['metric'],'failure_condition':trigger['condition']},
                    changed_knobs=[key+': '+str(json.loads((FOLDER/'draft-candidates'/suffix/'primary'/'plan.json').read_text())['knobs'][key])+' to '+str(value)
                        for key,value in plan['knobs'].items()
                        if value!=json.loads((FOLDER/'draft-candidates'/suffix/'primary'/'plan.json').read_text())['knobs'][key]])
                entry['candidates'].append(reference)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    return {'cases':len(manifest['cases']),'constructions':sum(1+len(x['candidates']) for x in manifest['cases']),
            'selected':False}


if __name__=='__main__':print(json.dumps(build()))
