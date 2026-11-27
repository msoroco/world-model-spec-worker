"""Build six exact route constructions from reviewed source requirements."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MODULES=('runner.py','native_entry.py','route_adapter.py','route_measure.py','analysis.py')
OFFLINE_TEST='''import json
import unittest
from pathlib import Path
from runner import check

class SelectedRouteOffline(unittest.TestCase):
    def test_exact_source_gate(self):
        root=Path(__file__).resolve().parents[1]
        selected=check(root)
        self.assertEqual(selected['case_id'],json.loads((root/'config.json').read_text())['selected_case_id'])
        self.assertIn('required enroute activity',selected['source_gate'])

if __name__=='__main__':unittest.main()
'''


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan=json.loads((HERE/'case-plan.json').read_text());ids=[row['case_id'] for row in plan['cases']]
    channels=[('municipal_route_designation','source','authoritative original municipal and street designation readback'),('ego_route_history','state','original 20 Hz route and road identity observations'),('enroute_context','state','original required enroute purpose, premises and activity source readback'),('governing_controls','state','original route controls and chapter scope review')]
    description={'channels':[{'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'900 original frames','reference_frame':'reviewed original truck-route street network','uncertainty':'physical source realization pending'} for name,unit,method in channels],
        'context_inputs':[{'name':'reviewed_truck_route_site','unit':'source','method':'independently reviewed designation, trip purpose and enroute premises'}],
        'limitations':['Worker does not assign a through-route or required-enroute legal verdict.','Stops and dwell alone do not prove pick-up, delivery or essential use.']}
    entries=[]
    for case in plan['cases']:
        cid=case['case_id'];short=cid.split('__')[-1];folder=HERE/'cases'/short
        config={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],'selected_case_id':cid,'supported_case_ids':ids,'required_atoms':[],'source_packets':[],'rate_hz':20,'duration_s':45,
            'cameras':[{'name':name,'width':size[0],'height':size[1],'fov_deg':75,'pose_strategy':'reviewed original route and enroute activity view'} for name,size in [('overview',(1920,1080)),('approach',(1280,720)),('reference_corner',(1280,720)),('driver_reference',(1280,720))]],
            'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl','position_key':'position_m','minimum_progress_m':5.0,'minimum_samples':3,'engineering_tolerances_not_legal':True,'completion_goal_method':'Original progress proxy; independent audit verifies actual two-truck-route passage and activity.'},
            'case':{'case_id':cid,'physical_target':'complete reviewed through-route or declared local control with source-backed enroute activity','recording_description':description}}
        spec={'case_id':cid,'street_class':case['street_class'],'route_use':case['route_use'],'enroute_purpose':case['enroute_purpose'],'source_status':'reviewed_original_route_packet_required_at_capture'}
        write(folder/'config.json',config);write(folder/'case-spec.json',spec)
        for candidate,speed in [('primary',4.0),('fallback1',5.5)]:
            controller={'target_speed_mps':speed,'source':'predeclared route tracking with original map road-ID readback','physical_acceptance':False}
            control_name='controller-'+candidate+'.json';write(folder/control_name,controller)
            files=[{'path':name,'source':str((HERE/name).relative_to(REPO)),'content':(HERE/name).read_text()} for name in MODULES]
            for name,value,source in [('config.json',config,folder/'config.json'),('case-spec.json',spec,folder/'case-spec.json'),('controller.json',controller,folder/control_name)]:
                files.append({'path':name,'source':str(source.relative_to(REPO)),'content':json.dumps(value,indent=2,sort_keys=True)+'\n'})
            files.append({'path':'tests/test_offline.py','content':OFFLINE_TEST})
            construction={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':plan['actor'],'case_id':cid,'entrypoint':'runner.py','files':files,'recording_description':description,
                'measurement_plan':{'selected_requirement':plan['requirement_dispositions'][0]['requirement'],'original_source':'reviewed original route designation, full path and enroute activity','saved_method':'source-bound origin-connector-destination route and purpose context'},
                'mechanisms':['authoritative reviewed original truck-route and connector source gate','same-tick vehicle road-ID and four-camera Native capture'],
                'static_checks':['exact case, 20 Hz, four cameras','reviewed source packet before Native mutation'],
                'termination_rules':{'duration_s':45,'early_termination':'retain failed capture; do not publish as original complete route'}}
            name='construction.json' if candidate=='primary' else 'fallback1-construction.json';digest=write(folder/name,construction)
            if candidate=='primary':
                entry={'case_id':cid,'construction':str((folder/name).relative_to(HERE)),'construction_sha256':digest,'kind':'delivery','measurement_procedure':{'entrypoint':'analysis.py'},'fixture_recipe':str((folder/'fixture-recipe.json').relative_to(REPO)),'measurement_contract':str((folder/'measurement-contract.json').relative_to(HERE)),
                    'acquisition':{name:{'entrypoint':'analysis.py','method':method,'evidence':'channels/'+name+'.jsonl'} for name,_,method in channels},
                    'candidate_risk':{'status':'physical','reason':'Original vehicle may not complete reviewed route within 45 seconds or remain in four camera views'},'candidates':[],
                    'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}
            else:
                entry['candidates'].append({'id':'fallback1','construction':str((folder/name).relative_to(HERE)),'construction_sha256':digest,
                    'trigger':{'source':'original route and four-view pixel audit','metric':'route completion','failure_condition':'primary missed origin-connector-destination route within 45 seconds'},
                    'changed_knobs':['target vehicle speed 4.0 to 5.5 m/s on unchanged site, route and purpose']})
        entries.append(entry)
        print(short,'primary/fallback1 source-deferred constructions',flush=True)
    write(HERE/'execution-manifest.draft.json',{'format':'worker-execution-manifest','assignment_id':HERE.name,'status':'reviewed_original_route_packet_required_at_capture','runtime_manifest_sha256':hashlib.sha256((REPO/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),'cases':entries})
    first=HERE/'cases'/plan['cases'][0]['case_id'].split('__')[-1]
    for name,source in [('construction.json','construction.json'),('config.json','config.json'),('case-spec.json','case-spec.json'),('controller.json','controller-primary.json')]:
        (HERE/name).write_bytes((first/source).read_bytes())
    (HERE/'tests/test_offline.py').write_text(OFFLINE_TEST)
    return entries

if __name__=='__main__':build()
