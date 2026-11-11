"""Package both C132497 cases and all four current-runtime candidates."""
import json
from pathlib import Path

import build_current_primary as base

ROOT, REPO = base.ROOT, base.REPO
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def package(case, candidate, recording):
    case_id = ROOT.name+'__'+case
    source = ROOT/'current-runtime-drafts'/case/candidate/'construction.json'
    construction = json.loads(source.read_text())
    files = construction['files']
    cfg = json.loads(next(item['content'] for item in files if item['path']=='config.json'))
    cfg.update({'selected_case_id':case_id,'duration_s':12,'required_atoms':[],
                'source_packets':[], 'cameras':['overview','approach',
                'reference_corner','driver_reference'], 'case':{'case_id':case_id},
                'physical_success_claimed':False})
    next(item for item in files if item['path']=='config.json')['content'] = json.dumps(cfg,indent=2)+'\n'
    road = next(item['content'] for item in files if item['path']=='right-exit-road.xodr')
    files.extend([{'path':'road.xodr','content':road},
                  {'path':'finalize_current.py',
                   'content':(ROOT/'native/finalize_current.py').read_text()}])
    construction['recording_description'] = recording
    construction['static_checks'] = ['240-frame source-bound request identity',
                                      'retained actor/trace/video frame join']
    construction['termination_rules'] = ['retain original acquisition',
                                          'require 240 synchronized frames']
    construction['mechanisms'] = ['counterclockwise two-lane roundabout request',
                                   'four synchronized source cameras']
    target = ROOT/'native/package-current'/case/candidate/'construction.json'
    base.write(target,construction)
    recipe, spec = base.diagnostic(construction,case_id,candidate)
    return target, recipe, spec


def main():
    batch = json.loads((REPO/'batch.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    channels = [{'name':name,'unit':unit,'sampling_rate_hz':20,
                 'method':'retained Native actor/frame join','time_window':'240 frames',
                 'reference_frame':'authored OpenDRIVE coordinates',
                 'uncertainty':'50 ms frame bracket; physical lane/exit unverified'}
                for name,unit in (('ego_pose','structured'),('ego_speed','m/s'),
                                  ('right_lane_exit','bool'))]
    recording = {'channels':channels,'context_inputs':[
        {'name':'authored_road','unit':'structured','method':'source-hashed OpenDRIVE'},
        {'name':'predeclared_intention','unit':'structured',
         'method':'controller intention hashed before motion'}],
        'limitations':['Native lane allocation, actual right exit, pixels and legal status unverified']}
    proposals = []
    results = []
    for case in CASES:
        case_id = ROOT.name+'__'+case
        names = ('roundabout_context','declared_right_exit','right_lane_exit')
        methods = ('measure_roundabout_context','measure_declared_right_exit',
                   'measure_right_lane_exit')
        types = ('object','boolean','boolean')
        requirements = [{'disposition_index':i,'requirement':row['requirement'],
                         'source':row['source'],'output_key':name,'method':method,
                         'value_type':typ,'kind':'measured',
                         'inputs':['native-raw-actors.jsonl']}
                        for i,(row,name,method,typ) in enumerate(zip(
                            plan['requirement_dispositions'],names,methods,types))]
        contract = {'format':'worker-measurement-contract','case_id':case_id,
                    'requirements':requirements,
                    'negative':{'remove':['native-raw-actors.jsonl'],
                                'error_contains':'Missing required source: native-raw-actors.jsonl'},
                    'uncertainty':{'frame_bracket_s':.05,
                                   'physical_and_legal_status':'unverified'}}
        contract_path = ROOT/'native/measurement-contracts-current'/(case+'.json')
        base.write(contract_path,contract)
        packages = {candidate: package(case,candidate,recording) for candidate in CANDIDATES}
        proposals.append({'case_id':case_id,'target_law_id':'LVMC-11-43-010-C2',
                          'target_type':'attempt','recording_description':recording})
        for selected in CANDIDATES:
            entry = {'case_id':case_id,'kind':'draft_not_selected',
                     'construction':packages['primary'][0].relative_to(ROOT).as_posix(),
                     'construction_sha256':base.sha(packages['primary'][0]),
                     'measurement_contract':contract_path.relative_to(ROOT).as_posix(),
                     'measurement_procedure':{'entrypoint':'finalize_current.py',
                                              'output_schema':'c132497-current-saved-diagnostic-v1'},
                     'fixture_recipe':packages[selected][1].relative_to(REPO).as_posix(),
                     'candidate_risk':{'status':'physical',
                         'reason':'Native road connectivity, governed right lane, actual exit and pixels unverified'},
                     'candidates':[]}
            offline = json.loads((ROOT/'draft-current-runtime-manifest.json').read_text())
            source_entry = next(e for e in offline['cases'] if e['case_id']==case_id)
            for fallback in CANDIDATES[1:]:
                item = next(x for x in source_entry['candidates'] if x['id']==fallback)
                entry['candidates'].append({'id':fallback,
                    'construction':packages[fallback][0].relative_to(ROOT).as_posix(),
                    'construction_sha256':base.sha(packages[fallback][0]),
                    'trigger':item['trigger'],'changed_knobs':item['changed_knobs']})
            manifest = {'format':'worker-unselected-current-runtime-candidate-v1',
                        'assignment_id':ROOT.name,'status':'draft_not_selected',
                        'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
                        'source_branch':'roundabout_right_exit','cases':[entry],
                        'original_native_observed':False,'delivery_ready':False}
            path = ROOT/f'draft-current-{case}-{selected}-manifest.json'
            base.write(path,manifest)
            results.append({'case_id':case_id,'candidate_id':selected,
                            'manifest':path.relative_to(ROOT).as_posix(),
                            'manifest_sha256':base.sha(path),
                            'construction_sha256':base.sha(packages[selected][0]),
                            'diagnostic_sha256':base.sha(packages[selected][2])})
    base.write(ROOT/'proposals/cases.json',{'cell_id':'C132497','actor':'motor_vehicle_driver',
               'status':'unselected_cpu_draft','cases':proposals})
    base.write(ROOT/'update015-current-candidate-index.json',
               {'format':'c132497-current-unselected-candidate-index-v1',
                'results':results,'physical_acceptance_claimed':False})
    return {'candidates':len(results),
            'index_sha256':base.sha(ROOT/'update015-current-candidate-index.json')}


if __name__ == '__main__':
    print(json.dumps(main(),sort_keys=True))
