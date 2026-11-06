"""Build eight exact unselected Native bundles for the right-turn pair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
SOURCES={'runner.py':'runner.py','geometry.py':'geometry.py','controller.py':'controller.py',
         'engineering.py':'engineering.py','measure.py':'measure.py','cameras.py':'cameras.py',
         'finalize.py':'finalize.py',
         'tests/test_native.py':'test_native.py'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    import importlib.util
    spec=importlib.util.spec_from_file_location('engineering',NATIVE/'engineering.py')
    eng=importlib.util.module_from_spec(spec);spec.loader.exec_module(eng)
    shared={target:(NATIVE/source).read_text() for target,source in SOURCES.items()}
    recording={'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
                'method':'Original Native actor/signal/map readback and full-frame join; authored intent separate',
                'time_window':'entire 24 s / 480-frame attempt',
                'reference_frame':'surveyed Native map and original frame identity',
                'uncertainty':'50 ms sampling; physical signal and pixel evidence required'}
               for name in json.loads((NATIVE/'config.json').read_text())['mandatory_channels']],
               'context_inputs':[],
               'limitations':['CPU source tests do not prove CARLA realization or accepted recording']}
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':FOLDER.name,'status':'draft_not_selected',
              'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
              'cases':[]}
    dispositions=json.loads((FOLDER/'case-plan.json').read_text())['requirement_dispositions']
    selected=(0,)
    methods=('measure_right_turn_permission',)
    outputs=('red_right_turn_permission',)
    proposals=[]
    for case in eng.CASES:
        case_id=FOLDER.name+'__'+case
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
                  'requirements':[{'disposition_index':index,
                                   'requirement':dispositions[index]['requirement'],
                                   'source':dispositions[index]['source'],
                                   'output_key':output_key,'method':method,
                                   'value_type':'object','kind':'measured',
                                   'inputs':['native_samples.jsonl','road_geometry.json']}
                                  for index,method,output_key in zip(selected,methods,outputs)],
                  'negative':{'remove':['road_geometry.json'],
                              'error_contains':'Missing required source: road_geometry.json'}}
        contract_path=FOLDER/'draft-candidates'/case/'measurement-contract.json'
        write(contract_path,contract)
        proposals.append({'case_id':case_id,'target_type':'attempt','recording_description':recording})
        entry={'case_id':case_id,'kind':'draft_not_selected',
               'candidate_risk':{'status':'physical','reason':'Signal mapping, actor behavior, frame coverage and pixels need original Native evidence'},
               'measurement_contract':str(contract_path.relative_to(FOLDER)),
               'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c110919-saved-analysis-v1'},
               'candidates':[]}
        for candidate in eng.CANDIDATES:
            config=json.loads((NATIVE/'config.json').read_text())
            config.update(case_id=case_id,selected_case_id=case_id,case_suffix=case,
                          candidate_id=candidate,knobs=eng.parameters(case,candidate)['knobs'],
                          supported_case_ids=[case_id],case={'case_id':case_id},
                          source_packets=[],recording_description=recording,
                          cameras=[{'name':n,'width':w,'height':h} for n,w,h in
                                   (('overview',1920,1080),('approach',1280,720),
                                    ('signal',1280,720),('destination',1280,720))])
            files=[{'path':name,'content':code} for name,code in shared.items()]
            files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
            construction={'case_id':case_id,'cell_id':'C110919','law_id':'NRS-484B-307-8d',
                          'actor':'motorcycle_or_moped_operator','entrypoint':'runner.py','files':files,
                          'recording_description':recording,
                          'mechanisms':['authored traffic-light right-turn OpenDRIVE',
                                        'observed-pose vehicle controller with case stop policy',
                                        'pedestrian yield actor and four synchronized lossless cameras'],
                          'termination_rules':['exact 480 original frames','capture and restoration errors retained'],
                          'status':'unselected_cpu_draft'}
            path=FOLDER/'draft-candidates'/case/candidate/'construction.json'
            write(path,construction)
            ref={'id':candidate,'construction':str(path.relative_to(FOLDER)),
                 'construction_sha256':sha(path)}
            if candidate=='primary':
                entry.update({key:ref[key] for key in ('construction','construction_sha256')})
            else:
                trigger=eng.TRIGGERS[candidate]
                ref.update(trigger={'source':trigger['source'],'metric':trigger['metric'],
                                    'failure_condition':f"{trigger['op']} {trigger['threshold']}"},
                           changed_knobs=[next(k for k,v in eng.CHANGES[candidate].items())])
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER/'draft-execution-manifest.json',manifest)
    write(FOLDER/'proposals'/'cases.json',{'format':'worker-draft-proposals-v1','cases':proposals,
                                          'status':'unselected'})
    return manifest

if __name__=='__main__':
    value=build()
    print(json.dumps({'cases':len(value['cases']),
                      'candidate_bundles':sum(1+len(e['candidates']) for e in value['cases']),
                      'status':value['status']}))
