"""Author a connected entry, quarter-circle, and left-exit road network."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
ARC_LENGTH=11*math.pi

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def road_xml(ident,name,x,y,heading,length,geometry,predecessor,successor):
    links=[]
    if predecessor is not None:
        links.append(f'<predecessor elementType="road" elementId="{predecessor}" contactPoint="end"/>')
    if successor is not None:
        links.append(f'<successor elementType="road" elementId="{successor}" contactPoint="start"/>')
    def lane_link(lane_id):
        elements=[]
        if predecessor is not None:elements.append(f'<predecessor id="{lane_id}"/>')
        if successor is not None:elements.append(f'<successor id="{lane_id}"/>')
        return '<link>'+''.join(elements)+'</link>'
    lanes='''<lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/><laneSection s="0"><left/>
      <center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
      <right><lane id="-1" type="driving" level="false">'''+lane_link(-1)+'''<width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" color="white" width="0.12"/></lane>
      <lane id="-2" type="driving" level="false">'''+lane_link(-2)+'''<width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right>
      </laneSection></lanes>'''
    return (f'<road name="{name}" length="{length:.12f}" id="{ident}" junction="-1">'
            f'<link>{"".join(links)}</link><type s="0" type="town"><speed max="20" unit="mph"/></type>'
            f'<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading:.12f}" length="{length:.12f}">{geometry}</geometry></planView>'
            f'{lanes}<objects/><signals/></road>')

def build():
    xml='<?xml version="1.0" standalone="yes"?>\n<OpenDRIVE>\n'
    xml+='<header revMajor="1" revMinor="4" name="C131364-left-exit-request" version="1.00" date="2026-11-08" north="40" south="-40" east="40" west="-40" vendor="worker"/>\n'
    xml+=road_xml(10,'south approach',-30,-22,0,30,'<line/>',None,11)+'\n'
    xml+=road_xml(11,'quarter circulatory arc',0,-22,0,ARC_LENGTH,'<arc curvature="0.045454545454545456"/>',10,12)+'\n'
    xml+=road_xml(12,'north left exit',22,0,math.pi/2,30,'<line/>',11,None)+'\n'
    xml+='</OpenDRIVE>\n'
    road=HERE/'left-exit-road.xodr';road.write_text(xml)
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    entries=[]
    for witness,lane,radius in (('witness_1',-1,23.75),('witness_2',-2,27.25)):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
            target=HERE/'exit-network-drafts'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            rows=[]
            arc_distance=radius*math.pi/2
            for i in range(240):
                time_s=(i+1)/20
                travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
                if travel<30:
                    phase='entry';x=-30+travel;y=-radius;heading=0;road_id=10
                elif travel<30+arc_distance:
                    phase='circulation';theta=-math.pi/2+(travel-30)/radius
                    x=radius*math.cos(theta);y=radius*math.sin(theta)
                    heading=math.degrees(theta+math.pi/2);road_id=11
                else:
                    phase='exit';x=radius;y=travel-30-arc_distance
                    heading=90;road_id=12
                rows.append({'frame':i,'time_s':time_s,'source_kind':'authored_native_request',
                             'witness':witness,'candidate_id':candidate,
                             'road_id':road_id,'phase':phase,'lane_id':lane,
                             'ego_x_m':round(x,6),'ego_y_m':round(y,6),
                             'ego_heading_deg':round(heading,6),
                             'ego_speed_mps':0 if candidate=='fallback3' and speed*time_s>12 else speed,
                             'intended_exit_kind':'left_turn','actual_exit_observed':False,
                             'roundabout_verified':False})
            track=target/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
            config={'format':'c131364-connected-left-exit-request-v1',
                    'assignment_id':CASE.name,'case_id':CASE.name+'__'+witness,
                    'candidate_id':candidate,'law_id':'LVMC-11-43-010-C1',
                    'cell_id':'C131364','rate_hz':20,'frames':240,
                    'road_sha256':sha(road),'tracks_sha256':sha(track),
                    'assignment_sha256':sha(assignment),'case_plan_sha256':sha(plan),
                    'requested_lane_id':lane,
                    'camera_policy':'elevated_overview_plus_four' if candidate=='fallback2' else 'four_views',
                    'connected_exit_authored':True,'original_native_observed':False,
                    'actual_exit_observed':False,'roundabout_verified':False,
                    'status':'unselected_native_request'}
            (target/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            entries.append({'case_id':config['case_id'],'candidate_id':candidate,
                            'config_sha256':sha(target/'config.json'),
                            'tracks_sha256':sha(track),'phases':sorted(set(row['phase'] for row in rows))})
    result={'format':'c131364-connected-exit-construction-v1',
            'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
            'case_plan_sha256':sha(plan),'road_sha256':sha(road),
            'entries':entries,'original_native_observed':False,
            'physical_roundabout_verified':False,'delivery_ready':False}
    (HERE/'exit-network-drafts'/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'requests':len(build()['entries'])}))
