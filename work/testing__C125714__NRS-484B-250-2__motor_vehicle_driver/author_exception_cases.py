"""Author distinct C125714 exception bundles and source-shaped CPU diagnostics."""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BASE = ROOT.name
KINDS = ('official_device_controlled','opposite_intends_left','opposite_makes_left')
SHARED = ('runner.py','native_crossing.py','exception_construction.py',
          'entry_timing.py','saved_finalizer.py','analysis.py','native_capture.py',
          'native_body_capture.py','branch_alternatives.py','controlled_yielding.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def enc(value):
    return json.dumps(value,separators=(',',':'),allow_nan=False)+'\n'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def body(x,y):
    return [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]]


def replace(value, old, new):
    if isinstance(value,str): return value.replace(old,new)
    if isinstance(value,list): return [replace(x,old,new) for x in value]
    if isinstance(value,dict): return {k:replace(v,old,new) for k,v in value.items()}
    return value


def main():
    manifest_path=ROOT/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    plan_path=ROOT/'case-plan.json';plan=json.loads(plan_path.read_text())
    proposal_path=ROOT/'proposals/cases.json';proposal=json.loads(proposal_path.read_text())
    inside=next(c for c in manifest['cases'] if c['case_id'].endswith('__timing_inside_training'))
    inside_id=inside['case_id']
    source=plan['requirement_dispositions'][0]['source']
    map_root=ET.fromstring((ROOT/'candidate-map.xodr').read_bytes())
    road=map_root.find("road[@id='10']")
    signals=ET.SubElement(road,'signals')
    ET.SubElement(signals,'signal',{'id':'C125714-signal-west','s':'20','t':'-1.75',
        'name':'engineering signal; authority review pending','dynamic':'yes',
        'orientation':'+','zOffset':'0','country':'US','type':'1000001',
        'subtype':'-1','value':'0','unit':'','height':'3','width':'.5'})
    map_path=ROOT/'cases/official_device_controlled/candidate-map.xodr'
    map_path.parent.mkdir(parents=True,exist_ok=True)
    map_path.write_bytes(ET.tostring(map_root,encoding='utf-8',xml_declaration=True)+b'\n')
    ids=[BASE+'__'+kind for kind in KINDS]
    all_ids=[c['case_id'] for c in manifest['cases']]+ids
    for kind in KINDS:
        case_id=BASE+'__'+kind;folder=ROOT/'cases'/kind
        folder.mkdir(parents=True,exist_ok=True)
        scene=copy.deepcopy(json.loads((ROOT/'cases/timing_inside_training/scene.json').read_text()))
        scene['case_id']=case_id
        scene['requested_entry_offset_s']=-.02500000037252903
        scene['other_left_turn_intent']=kind!='official_device_controlled'
        scene['other_left_turn_making']=kind=='opposite_makes_left'
        scene['official_device_controls_intersection']=kind=='official_device_controlled'
        if kind=='official_device_controlled':
            scene['official_device_id']='C125714-signal-west'
            scene['map_source_sha256']=sha(map_path)
            scene['map_source']='candidate-map.xodr'
        else:
            scene['ego_highway']='authored divided highway A'
            scene['other_highway']=scene['ego_highway']
            scene['approach_relation']='opposite'
            scene['other_route_xyz_m']=[[25,4,0],[0,4,0],
                [0,-18,0] if kind=='opposite_makes_left' else [-25,4,0]]
            scene['cameras'][2]['pose_strategy']='opposite east approach and left-turn connector'
        write(folder/'scene.json',scene)
        config=copy.deepcopy(json.loads((ROOT/'cases/timing_inside_training/config.json').read_text()))
        config['selected_case_id']=case_id
        config['supported_case_ids']=all_ids
        config['case']['case_id']=case_id
        config['case']['requested_entry_offset_s']=scene['requested_entry_offset_s']
        config['cameras']=scene['cameras']
        config['case']['recording_description']['limitations'].append(
            'Exception context and actual motion require original source review; fixture fields are not legal findings.')
        write(folder/'config.json',config)
        construction=copy.deepcopy(json.loads((ROOT/inside['construction']).read_text()))
        construction['case_id']=case_id
        construction['recording_description']=config['case']['recording_description']
        files={f['path']:f for f in construction['files']}
        for name,path in [('scene.json',folder/'scene.json'),('config.json',folder/'config.json'),
                          ('candidate-map.xodr',map_path if kind=='official_device_controlled'
                           else ROOT/'candidate-map.xodr')]:
            files[name]['source']=str(path.relative_to(REPO))
            files[name]['content']=path.read_text()
        for name in SHARED:
            path=ROOT/name
            if name in files: files[name]['content']=path.read_text()
            else: construction['files'].append({'path':name,'source':str(path.relative_to(REPO)),
                                               'content':path.read_text()})
        write(folder/'construction.json',construction)
        contract=copy.deepcopy(json.loads((ROOT/inside['measurement_contract']).read_text()))
        contract['case_id']=case_id
        contract['requirements'][0]['disposition_index']=1 if kind=='official_device_controlled' else 2
        contract['requirements'][0]['requirement']=plan['requirement_dispositions'][
            contract['requirements'][0]['disposition_index']]['requirement']
        contract['requirements'][0]['method']='measure_original'
        contract['requirements'][0]['source']=source
        contract['unresolved_judgments']+=['whether statutory exception applies in physical source']
        write(folder/'measurement-contract.json',contract)
        entry=replace(copy.deepcopy(inside),inside_id,case_id)
        entry=replace(entry,'timing_inside_training',kind)
        entry['construction']=str((folder/'construction.json').relative_to(ROOT))
        entry['construction_sha256']=sha(folder/'construction.json')
        entry['measurement_contract']=str((folder/'measurement-contract.json').relative_to(ROOT))
        entry['fixture_recipe']=str((folder/'diagnostic-recipe.json').relative_to(REPO))
        entry['proof_status']='exception_exact_construction_proofs_pending'
        entry['offline']={};entry['compatibility']={};entry['negative']={}
        entry['physical_preparation']={};entry['delivery_acceptance']={}
        entry['post_capture']['test_exit_code']=None
        entry['post_capture']['test_log_sha256']=None
        entry['candidate_risk']={'status':'physical','reason':
            'Two-vehicle spawn at reviewed median-opening waypoint can fail before exception motion; alternate nearby ego waypoint retains the fact pattern.'}
        entry['candidates']=[]
        manifest['cases'].append(entry)
        plan_case=replace(copy.deepcopy(next(c for c in plan['cases'] if c['case_id']==inside_id)),inside_id,case_id)
        plan_case['target_type']='statutory_exception_fact_probe'
        plan_case['planned_entry_time_difference_s']=-.02500000037252903
        plan_case['preparation_status']='exact_exception_construction_cpu_proofs_pending'
        plan_case['measurement_source']='entry_timing.py and branch_alternatives.py over original Native body and reviewed context sources'
        plan_case['physical_risk']='Device authority or opposite left-turn motion may not materialize; original map and motion must be reviewed'
        plan['cases'].append(plan_case)
        proposal_case=replace(copy.deepcopy(next(c for c in proposal['cases'] if c['case_id']==inside_id)),inside_id,case_id)
        proposal_case['target_type']='exception_probe'
        proposal_case['rationale']='Source-bound diagnostic of '+kind.replace('_',' ')+' with legal applicability unresolved.'
        proposal_case['recording_description']=construction['recording_description']
        proposal_case.pop('paired_probe_id',None);proposal_case.pop('probe',None)
        proposal_case.pop('deliberate_differences',None)
        proposal['cases'].append(proposal_case)
        diagnostic=copy.deepcopy(json.loads((ROOT/'diagnostic.json').read_text()))
        data=diagnostic['files'];site=json.loads(data['site-context.json'])
        site.update(case_id=case_id,map_sha256=scene['map_source_sha256'],
                    ego_highway=scene['ego_highway'],other_highway=scene['other_highway'],
                    approach_relation=scene['approach_relation'],
                    official_device_controls_intersection=scene['official_device_controls_intersection'],
                    other_left_turn_intent=scene['other_left_turn_intent'],
                    other_left_turn_making=scene['other_left_turn_making'])
        if kind=='official_device_controlled':site['official_device_id']=scene['official_device_id']
        data['site-context.json']=enc(site)
        other=[]
        for i,line in enumerate(data['other-body-history.jsonl'].splitlines()):
            row=json.loads(line)
            if kind=='opposite_intends_left':
                x,y=(10,4) if i<5 else ((0,4) if i<72 else (-10,4))
            elif kind=='opposite_makes_left':
                x,y=(10,4) if i<5 else ((0,4) if i<40 else (0,-10))
            else: continue
            row['body_vertices_xy_m']=body(x,y);other.append(enc(row))
        if other:data['other-body-history.jsonl']=''.join(other)
        control=[{'frame':i,'time_s':i/20,'ego_brake':1.0 if i<4 else 0.0,
                  'other_brake':1.0 if i<5 else 0.0,'control_policy':'timed_release'}
                 for i in range(75)]
        data['controller-history.jsonl']=''.join(enc(row) for row in control)
        road_bytes=(map_path if kind=='official_device_controlled' else ROOT/'candidate-map.xodr').read_bytes()
        bindings={name:{'kind':'diagnostic_fixture','sha256':hashlib.sha256(
            (road_bytes if name=='road.xodr' else data[name].encode())).hexdigest()}
            for name in ('road.xodr','site-context.json','ego-body-history.jsonl',
                         'other-body-history.jsonl','controller-history.jsonl','video_frames.jsonl')}
        data['original-bindings.json']=enc(bindings)
        data['acquisition.json']=enc({name:{'kind':'diagnostic_fixture',
            'sha256':hashlib.sha256(value.encode()).hexdigest()}
            for name,value in data.items() if name!='acquisition.json'})
        cap=json.loads(data['capture/manifest.json']);cap['case_id']=case_id
        cap['sources']['road.xodr']=hashlib.sha256(road_bytes).hexdigest()
        data['capture/manifest.json']=enc(cap)
        write(folder/'diagnostic.json',diagnostic)
        recipe={'format':'worker-fixture-recipe','sources':[{'path':'road.xodr',
            'source':str((map_path if kind=='official_device_controlled' else ROOT/'candidate-map.xodr').relative_to(REPO)),
            'sha256':hashlib.sha256(road_bytes).hexdigest()}],
            'generator':{'source':str((folder/'diagnostic.json').relative_to(REPO)),
                         'sha256':sha(folder/'diagnostic.json')}}
        write(folder/'diagnostic-recipe.json',recipe)
    plan['requirement_dispositions'][1]['status']='selected_required'
    plan['requirement_dispositions'][1]['case_ids']=[ids[0]]
    plan['requirement_dispositions'][1]['evidence_or_gap']='Exact governing-device construction and diagnostic authored; original authority and motion pending.'
    plan['requirement_dispositions'][2]['status']='selected_required'
    plan['requirement_dispositions'][2]['case_ids']=ids[1:]
    plan['requirement_dispositions'][2]['evidence_or_gap']='Opposite intent and realized left-turn constructions and diagnostics authored; original review pending.'
    for item,assigned in zip(plan['branch_decomposition'][1:3],([ids[0],ids[1:]])):
        item['status']='exact_exception_construction_cpu_proofs_pending';item['case_ids']=assigned
    plan['comparisons'] += [
        {'comparison_id':'device_governance_exception','case_ids':[inside_id,ids[0]],
         'fixed_conditions':['same crossing','same two highways','same entry timing and capture channels'],
         'deliberate_differences':['reviewed official device governance'],
         'status':'planned_unexecuted_source_measurement_cpu_tested'},
        {'comparison_id':'opposite_turn_realization','case_ids':ids[1:],
         'fixed_conditions':['same opposite approaches','same highway','same intent and capture channels'],
         'deliberate_differences':['other driver makes left turn versus intends only'],
         'status':'planned_unexecuted_source_measurement_cpu_tested'}]
    root_config=json.loads((ROOT/'config.json').read_text());root_config['supported_case_ids']=all_ids
    write(ROOT/'config.json',root_config)
    for entry in manifest['cases'][:5]:
        for target in [entry]+entry.get('candidates',[]):
            construction=json.loads((ROOT/target['construction']).read_text())
            files={f['path']:f for f in construction['files']}
            if 'exception_construction.py' not in files:
                construction['files'].append({'path':'exception_construction.py',
                    'source':str((ROOT/'exception_construction.py').relative_to(REPO)),
                    'content':(ROOT/'exception_construction.py').read_text()})
            write(ROOT/target['construction'],construction)
    root_construction=json.loads((ROOT/'construction.json').read_text())
    root_files={f['path']:f for f in root_construction['files']}
    if 'exception_construction.py' not in root_files:
        root_construction['files'].append({'path':'exception_construction.py',
            'source':str((ROOT/'exception_construction.py').relative_to(REPO)),
            'content':(ROOT/'exception_construction.py').read_text()})
    write(ROOT/'construction.json',root_construction)
    write(plan_path,plan);write(proposal_path,proposal);write(manifest_path,manifest)
    index=json.loads((ROOT/'proposals/semantic-index.json').read_text())
    index['stages']['cases']['sha256']=sha(proposal_path)
    write(ROOT/'proposals/semantic-index.json',index)
    print('authored exception case bundles:',*ids)


if __name__=='__main__':main()
