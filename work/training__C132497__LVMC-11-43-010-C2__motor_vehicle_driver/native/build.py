"""Author a connected clockwise quarter-arc right-exit request for LVMC C2."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
LANES={'reference':(-2,16.75),'contrast':(-1,20.25)}
POLICIES={'primary':(8,'standard',None),
          'fallback1':(6.5,'standard',None),
          'fallback2':(8,'elevated_overview',None),
          'fallback3':(3,'standard',12)}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def road(ident,name,x,y,heading,length,geometry,previous,next_):
    links=''
    if previous is not None:links+=f'<predecessor elementType="road" elementId="{previous}" contactPoint="end"/>'
    if next_ is not None:links+=f'<successor elementType="road" elementId="{next_}" contactPoint="start"/>'
    lanes=[]
    for lane in (-1,-2):
        lane_links='<link>'
        if previous is not None:lane_links+=f'<predecessor id="{lane}"/>'
        if next_ is not None:lane_links+=f'<successor id="{lane}"/>'
        lane_links+='</link>'
        lanes.append(f'<lane id="{lane}" type="driving" level="false">{lane_links}'
                     '<width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
                     '<roadMark sOffset="0" type="broken" color="white" width="0.12"/></lane>')
    return (f'<road name="{name}" length="{length:.12f}" id="{ident}" junction="-1">'
            f'<link>{links}</link><type s="0" type="town"><speed max="20" unit="mph"/></type>'
            f'<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading:.12f}" length="{length:.12f}">{geometry}</geometry></planView>'
            '<lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><left/>'
            '<center><lane id="0" type="none" level="false"/></center><right>'+
            ''.join(lanes)+'</right></laneSection></lanes><objects/><signals/></road>')

def build():
    xml='<?xml version="1.0" standalone="yes"?>\n<OpenDRIVE>\n'
    xml+='<header revMajor="1" revMinor="4" name="C132497-right-exit-request" version="1.00" date="2026-11-08" north="50" south="-60" east="60" west="-30" vendor="worker"/>\n'
    xml+=road(20,'south entry',0,-52,math.pi/2,30,'<line/>',None,21)+'\n'
    xml+=road(21,'clockwise quarter arc',0,-22,math.pi/2,11*math.pi,'<arc curvature="-0.045454545454545456"/>',20,22)+'\n'
    xml+=road(22,'east right exit',22,0,0,30,'<line/>',21,None)+'\n</OpenDRIVE>\n'
    road_path=HERE/'right-exit-road.xodr';road_path.write_text(xml)
    assignment=ROOT/'inputs'/CASE.name/'assignment.json';plan=CASE/'case-plan.json'
    entries=[]
    for witness,(lane,radius) in LANES.items():
        for candidate,(speed,camera,stop) in POLICIES.items():
            target=HERE/'drafts'/witness/candidate;target.mkdir(parents=True,exist_ok=True)
            rows=[]
            for i in range(240):
                t=(i+1)/20;distance=speed*t if stop is None else min(stop,speed*t)
                if distance<30:
                    phase='entry';road_id=20;x=22-radius;y=-52+distance;heading=90
                elif distance<30+radius*math.pi/2:
                    phase='circulation';road_id=21
                    theta=math.pi-(distance-30)/radius
                    x=22+radius*math.cos(theta);y=-22+radius*math.sin(theta)
                    heading=math.degrees(theta-math.pi/2)
                else:
                    phase='exit';road_id=22;x=22+distance-30-radius*math.pi/2
                    y=-22+radius;heading=0
                rows.append({'frame':i,'time_s':t,'source_kind':'authored_native_request',
                    'witness':witness,'candidate_id':candidate,'phase':phase,
                    'road_id':road_id,'lane_id':lane,
                    'ego_x_m':round(x,6),'ego_y_m':round(y,6),
                    'ego_heading_deg':round(heading,6),
                    'ego_speed_mps':0 if stop is not None and speed*t>stop else speed,
                    'intended_exit_kind':'right_turn','actual_exit_observed':False,
                    'physical_roundabout_verified':False})
            track=target/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
            config={'format':'c132497-right-exit-request-v1','assignment_id':CASE.name,
                'case_id':CASE.name+'__'+witness,'candidate_id':candidate,
                'law_id':'LVMC-11-43-010-C2','cell_id':'C132497',
                'actor':'motor_vehicle_driver','rate_hz':20,'frames':240,
                'road_sha256':sha(road_path),'tracks_sha256':sha(track),
                'assignment_sha256':sha(assignment),'case_plan_sha256':sha(plan),
                'requested_lane_id':lane,'requested_arc_radius_m':radius,
                'camera_policy':camera,'requested_speed_mps':speed,
                'stop_distance_m':stop,'connected_right_exit_authored':True,
                'original_native_observed':False,'actual_exit_observed':False,
                'physical_roundabout_verified':False,'status':'unselected_native_request'}
            (target/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            entries.append({'case_id':config['case_id'],'candidate_id':candidate,
                'config_sha256':sha(target/'config.json'),'tracks_sha256':sha(track),
                'phases':sorted(set(row['phase'] for row in rows))})
    manifest={'format':'c132497-right-exit-construction-v1',
        'assignment_id':CASE.name,'road_sha256':sha(road_path),
        'entries':entries,'original_native_observed':False,
        'physical_roundabout_verified':False,'delivery_ready':False}
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps({'drafts':len(build()['entries'])}))
