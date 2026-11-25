"""Derive a transparent CPU contrast from the retained right-turn diagnostic.

The adjacent-lane samples are synthetic and do not assert Native execution.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('selected_geometry',HERE/'selected-geometry-in-cell.py')
geometry_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry_module)
route=geometry_module.route


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path,values):path.write_text(''.join(json.dumps(x)+'\n' for x in values))


def main():
    source=HERE/'selected-source/controlled_1'
    target=HERE/'selected-source/controlled_2'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source,target)
    trace=rows(target/'trace.jsonl')
    evidence=rows(target/'capture/evidence.jsonl')
    samples=rows(target/'native_samples.jsonl')
    bodies=rows(target/'body_history.jsonl')
    points=route(-1.75)
    start=round(((-7)+50)/.1)
    curve=[[x,-y] for x,y in points[start:start+151]]
    assert len(curve)==151
    for i in range(480):
        if i<160:
            x=-40+33*i/159;y=1.75;angle=0;road=1;lane=-1
        elif i<320:
            j=round(150*(i-160)/159)
            x,y=curve[j]
            before=curve[max(0,j-1)];after=curve[min(150,j+1)]
            angle=math.atan2(after[1]-before[1],after[0]-before[0]);road=13;lane=-2
        else:
            x=-5.25;y=7.3+32.7*(i-320)/159;angle=math.pi/2;road=4;lane=-2
        fx,fy=math.cos(angle),math.sin(angle)
        rx,ry=-fy,fx
        corners=[[x+d*2.6*fx+s*1.1*rx,y+d*2.6*fy+s*1.1*ry]
                 for d,s in ((-1,-1),(-1,1),(1,1),(1,-1))]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        samples[i].update(native_center_xy_m=[x,y],native_forward_xy=[fx,fy],
                          native_body_xy_m=corners,native_road_id=road,native_lane_id=lane)
        bodies[i]['body_vertices_m']=body
        trace[i].update(position={'x':x,'y':y,'z':0.5},position_m=[x,y,0.5],
                        heading_deg=math.degrees(angle),velocity_mps=[5*fx,5*fy,0])
        evidence[i]['ego'].update(body_vertices_m=body,position_m=[x,y,0.5],
                                  heading_deg=math.degrees(angle))
        projection=evidence[i]['world']['road_projection']
        projection.update(road_id=road,lane_id=lane)
        if road==1:
            projection['s_m']=x+100
    for rel,value in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('native_samples.jsonl',samples),('body_history.jsonl',bodies)]:
        write_rows(target/rel,value)
    geometry=json.loads((target/'road_geometry.json').read_text())
    geometry['adjacent_approach_lane_id']=-1
    (target/'road_geometry.json').write_text(json.dumps(geometry)+'\n')
    (target/'context.json').write_text(json.dumps({'surveyed_right_turn_lane_intersection':geometry})+'\n')
    manifest=json.loads((target/'capture/manifest.json').read_text())
    manifest['sources']['trace.jsonl']=sha(target/'trace.jsonl')
    (target/'capture/manifest.json').write_text(json.dumps(manifest)+'\n')
    assert len(trace)==len(evidence)==len(samples)==len(bodies)==480
    print(json.dumps({'source':'controlled_2','frames':480,
        'first_approach_lane_id':samples[0]['native_lane_id'],
        'exit_road_id':samples[-1]['native_road_id'],
        'native_executed':False}))


if __name__=='__main__':main()
