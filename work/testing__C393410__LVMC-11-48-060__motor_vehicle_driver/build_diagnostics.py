"""Build exact synthetic route diagnostics for six C393410 cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
EXAMPLE=REPO/'runtime/fixtures/example.json'


def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build():
    plan=json.loads((HERE/'case-plan.json').read_text());example=json.loads(EXAMPLE.read_text())
    for case in plan['cases']:
        cid=case['case_id'];short=cid.split('__')[-1];folder=HERE/'cases'/short
        diagnostic=json.loads(json.dumps(example));files=diagnostic['files']
        capture=json.loads(files['capture/manifest.json']);capture['case_id']=cid;files['capture/manifest.json']=json.dumps(capture,sort_keys=True)+'\n'
        mapping=[json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        source_hash=sha(('synthetic-truck-route:'+short).encode())
        routes={'origin':{'road_id':10,'designation_source_sha256':source_hash},'destination':{'road_id':30,'designation_source_sha256':source_hash}}
        site={'municipal_jurisdiction_reviewed':True,'chapter_scope_reviewed':True,'truck_routes':routes,'intervening_street':{'road_id':20,'designation':case['street_class'],'designation_source_sha256':source_hash},'governing_controls_reviewed':True}
        purpose={'kind':case['enroute_purpose'],'required_enroute_reviewed':case['enroute_purpose']!='none'}
        if case['enroute_purpose']!='none':purpose.update({'premises_source_sha256':source_hash,'activity_source_sha256':source_hash})
        frames=[]
        for index,row in enumerate(mapping):
            road_id=10 if index<2 else (30 if index>=len(mapping)-2 and case['route_use']=='through' else 20)
            designation=case['street_class'] if road_id==20 else 'truck_route'
            frames.append({'frame':row['carla_frame'],'time_s':row['time_s'],'ego_actor_id':1,'position_xy_m':[float(index*10),0.0],'road_id':road_id,'street_designation':designation,
                'activity_kind':purpose['kind'] if index==4 and purpose['kind']!='none' else None,'observation_source':'synthetic_diagnostic'})
        itinerary={'route_use':case['route_use'],'waypoints_xy_m':[[0,0],[40,0],[80,0]],'origin_on_truck_route':True,'entered_intervening_street':True,'destination_on_truck_route':case['route_use']=='through','local_destination_reviewed':case['route_use']=='local'}
        packet={'format':'worker-reviewed-truck-route-site','assignment_id':HERE.name,'case_id':cid,'diagnostic_fixture':True,'source_provenance':{'kind':'diagnostic_fixture','files':[{'path':'synthetic.txt','sha256':source_hash}]},'original_trace_id':'synthetic-diagnostic-trace','site_source_sha256':source_hash,'site':site,'itinerary':itinerary,'enroute_purpose':purpose,'fps':20,'frames':frames}
        text=json.dumps(packet,sort_keys=True)+'\n';files['original-route-observations.json']=text
        files['original-route-receipt.json']=json.dumps({'case_id':cid,'fps':20,'frame_count':len(frames),'diagnostic_fixture':True,'source_sha256':sha(text.encode())},sort_keys=True)+'\n'
        files['fixture-provenance.json']=json.dumps({'case_id':cid,'scope':'Synthetic route software diagnostic; no original designation, activity or legal evidence'},sort_keys=True)+'\n'
        path=folder/'diagnostic.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(diagnostic,separators=(',',':'))+'\n')
        relative=str(path.relative_to(REPO))
        write(folder/'fixture-recipe.json',{'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':relative,'sha256':sha(path.read_bytes())}],
            'generator':{'source':relative,'sha256':sha(path.read_bytes())}})
        keys={0:('scope','measure_scope'),1:('pickup_context','measure_pickup'),2:('delivery_context','measure_delivery'),3:('essential_context','measure_essential'),4:('route_control','measure_route_control')}
        requirements=[]
        for index,requirement in enumerate(plan['requirement_dispositions']):
            if cid not in requirement['case_ids']:continue
            key,method=keys[index]
            requirements.append({'disposition_index':index,'requirement':requirement['requirement'],'source':requirement['source'],'output_key':key,'method':method,'value_type':'object','kind':'measured','inputs':['original-route-observations.json','original-route-receipt.json']})
        write(folder/'measurement-contract.json',{'format':'worker-measurement-contract','case_id':cid,
            'requirements':requirements,
            'negative':{'remove':['original-route-observations.json'],'error_contains':'Missing required source: original-route-observations.json'}})
        print(short,'synthetic route source/contract prepared',flush=True)

if __name__=='__main__':build()
