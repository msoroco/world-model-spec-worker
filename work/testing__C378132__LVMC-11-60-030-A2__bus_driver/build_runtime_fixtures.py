"""Build source-shaped A2 bus loading-stop diagnostics for pinned runtime compatibility."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from analysis import trace_row

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
AID=ROOT.name
VIEWS=('overview','approach','reference_corner','driver_reference')
SIZES={'overview':(1920,1080),'approach':(1280,720),
       'reference_corner':(1280,720),'driver_reference':(1280,720)}
TEMPLATE=REPO/'work/testing__C378245__LVMC-11-60-040__taxi_driver/cases/outside_stand_park/diagnostic-sources'


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan=json.loads((ROOT/'case-plan.json').read_text())
    event_template=json.loads((TEMPLATE/'capture/evidence.jsonl').read_text().splitlines()[0])
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        folder=ROOT/'cases'/suffix
        source=folder/'fixture-sources';source.mkdir(parents=True,exist_ok=True)
        for name in ('site','designation','route','identity','activity','purpose','circumstances','native'):
            value=json.loads((folder/'diagnostic-sources'/(name+'.json')).read_text())
            if name=='native':
                for row in value['frames']:
                    row['original_frame']=row['frame']
            write(source/(name+'.json'),value)
        refs={name:{'path':name+'.json','sha256':sha(source/(name+'.json'))}
              for name in ('site','designation','route','identity','activity','purpose','circumstances','native')}
        packet={'assignment_id':AID,'case_id':case['case_id'],'cell_id':'C378132',
                'law_id':'LVMC-11-60-030-A2','actor':'bus_driver',
                'diagnostic_fixture':True,
                **{key:case[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')},
                'source_refs':refs}
        write(source/'location-source-packet.json',packet)
        native=json.loads((source/'native.json').read_text())
        rows=native['frames']
        trace=''.join(json.dumps(trace_row(i,row),sort_keys=True)+'\n' for i,row in enumerate(rows))
        (source/'trace.jsonl').write_text(trace)
        mapping=[{'video_frame':i,'carla_frame':i,'native_frame':i,'time_s':i/20} for i in range(900)]
        (source/'video_frames.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in mapping))
        road=(TEMPLATE/'road.xodr').read_text().replace('C378245','C378132')
        (source/'road.xodr').write_text(road)
        events=[];graph_frames=[];graphs=[]
        for i,row in enumerate(rows):
            event=copy.deepcopy(event_template)
            event.update(original_frame=i,replay_frame=i,actor_id=305,
                         recording_time_s=i/20,replay_simulation_time_s=i/20)
            body=[[x,y,z] for x,y in row['bus_footprint_xy_m'] for z in (0.0,2.5)]
            event['ego'].update(position_m=[*row['bus_center_xy_m'],0.0],heading_deg=0.0,
                                speed_mps=row['bus_speed_mps'],speed_provenance='synthetic_native_sample',
                                body_vertices_m=body)
            event['original_observations'].update(frame=i,time_s=i/20)
            events.append(event)
            graph_path=f'capture/native/graphs/base/{i:08d}.adapter.json'
            graph_frames.append({'frame':i,'simulation_time':i/20,'abstract':None,'base':None,
                                 'nodes':0,'edges':0,'extraction_seconds':0.0,'capture_seconds':0.0,
                                 'adapter_graph':f'graphs/base/{i:08d}.adapter.json'})
            graphs.append({'path':graph_path,
                           'attributes':{'frame':i,'simulation_time_s':i/20,
                                         'observed_evidence':event['original_observations']},
                           'nodes':[],'edges':[]})
        capture=source/'capture';(capture/'native').mkdir(parents=True,exist_ok=True)
        (capture/'evidence.jsonl').write_text(''.join(json.dumps(e,separators=(',',':'),sort_keys=True)+'\n' for e in events))
        (capture/'native/frames.jsonl').write_text(''.join(json.dumps(e,separators=(',',':'),sort_keys=True)+'\n' for e in graph_frames))
        (capture/'recorder_info.txt').write_text('Version: 1\nMap: OpenDriveMap\n Create 305: vehicle.bus (0) at (0, 0, 0)\n')
        (source/'carla_recorder.log').write_text('Synthetic diagnostic bus recorder identity '+suffix+'\n')
        map_facts=capture/'native_map_facts.json'
        write(map_facts,{'map':'Carla/Maps/OpenDriveMap','junctions':[],
                         'crosswalk_vertices_m':[],'crosswalk_inventory_scope':'synthetic diagnostic'})
        write(capture/'manifest.json',{'status':'draft','acquisition':'synthetic_fixture',
              'case_id':case['case_id'],'source_run':'synthetic C378132 A2 CPU fixture',
              'map':'Carla/Maps/OpenDriveMap','frames':900,'required_observations':[],
              'extraction_confirmed':True,'complete_driving_lanes':True,
              'observation_contract_version':2,'road_user_visibility_observed':False,
              'speed_source':'synthetic Native sample','frame_join':'same synthetic diagnostic frame',
              'visibility_scope':'diagnostic only',
              'native_map_facts':{'path':'native_map_facts.json','sha256':sha(map_facts)},
              'sources':{'road.xodr':sha(source/'road.xodr'),
                         'trace.jsonl':hashlib.sha256(trace.encode()).hexdigest(),
                         'carla_recorder.log':sha(source/'carla_recorder.log')}})
        listed=[p for p in source.rglob('*') if p.is_file()]
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':str(p.relative_to(source)),
                            'source':str(p.relative_to(REPO)), 'sha256':sha(p)}
                           for p in sorted(listed)]}
        spec={'files':{},'graphs':graphs,
              'videos':[{'path':name+'.mkv','frames':900,'width':SIZES[name][0],
                         'height':SIZES[name][1],'fps':20,'color':'black'} for name in VIEWS]}
        spec_path=folder/'diagnostic.json';write(spec_path,spec)
        recipe['generator']={'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}
        write(folder/'fixture-recipe.json',recipe)
    print(f"{len(plan['cases'])} source-shaped 900-frame bus fixture recipes built")

if __name__=='__main__':
    build()
