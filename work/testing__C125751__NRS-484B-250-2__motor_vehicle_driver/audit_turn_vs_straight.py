"""Independent synthetic source comparison for C125751 opposite turn and straight."""
import hashlib
import json
import math
from pathlib import Path

P=Path('work/testing__C125751__NRS-484B-250-2__motor_vehicle_driver')

def load(name):
    return json.loads((P/name).read_text())

def check_source(recipe_name):
    recipe=load(recipe_name)
    assert hashlib.sha256(Path(recipe['generator']['source']).read_bytes()).hexdigest()==recipe['generator']['sha256']
    for item in recipe['sources']:
        assert hashlib.sha256(Path(item['source']).read_bytes()).hexdigest()==item['sha256'],item['path']
    return recipe

def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]

def center(body):
    v=body['body_vertices_xy_m'];return (sum(q[0] for q in v)/4,sum(q[1] for q in v)/4)

def check_motion(series,role,terminal,turn):
    pts=[center(r['actor_sources'][role]) for r in series]
    assert math.dist(pts[0],(-8,0) if role=='ego' else (8,0))<1e-6
    assert math.dist(pts[-1],terminal)<1e-6
    assert max(math.dist(a,b) for a,b in zip(pts,pts[1:]))<=.26
    heads=[r['actor_sources'][role]['heading_deg'] for r in series]
    if role=='ego':
        assert abs(heads[0])<1e-6 and abs(heads[-1]-(90 if turn else 0))<1e-6
        if turn:
            assert all(a<=b+1e-6 for a,b in zip(heads,heads[1:]))
            assert sum(y2>y1+1e-3 for (_,y1),(_,y2) in zip(pts,pts[1:]))>=30
    return pts

def run():
    turn_recipe=check_source('opposite-turn-v2-recipe.json')
    straight_recipe=check_source('straight-diagnostic-recipe.json')
    manifest=load('execution-manifest.json')
    selected={entry['case_id'].rsplit('__',1)[-1]:entry for entry in manifest['cases']}
    assert {'opposite_left_turn','opposite_straight_comparator'} <= set(selected)
    assert selected['opposite_left_turn']['fixture_recipe']==str(P/'opposite-turn-v2-recipe.json')
    assert selected['opposite_straight_comparator']['fixture_recipe']==str(P/'straight-diagnostic-recipe.json')
    for suffix in ('opposite_left_turn','opposite_straight_comparator'):
        entry=selected[suffix]
        assert hashlib.sha256((P/entry['construction']).read_bytes()).hexdigest()==entry['construction_sha256']
    turn_spec=load('opposite-turn-v2-fixture-spec.json')['files']
    straight_spec=load('straight-diagnostic-fixture-spec.json')['files']
    for field in ('road.xodr','signal_history.jsonl','video_frames.jsonl'):
        assert turn_spec[field]==straight_spec[field],field
    for field in ('road_geometry.json','signal_context.json','stop_context.json'):
        a=json.loads(turn_spec[field]);b=json.loads(straight_spec[field]);a.pop('site_review_sha256',None);b.pop('site_review_sha256',None)
        assert a==b,field
    a=json.loads(turn_spec['turn_route_context.json'])['routes'];b=json.loads(straight_spec['turn_route_context.json'])['routes']
    assert a['other']==b['other'] and a['ego'][:-1]==b['ego'][:-1]
    assert a['ego'][-1]==[0,10] and b['ego'][-1]==[10,0]
    turn=rows(P/'opposite-turn-v2-sources/body_history.jsonl');straight=rows(P/'straight-diagnostic-sources/body_history.jsonl')
    assert len(turn)==len(straight)==1100
    assert [r['native_frame'] for r in turn]==[r['native_frame'] for r in straight]==list(range(100,1200))
    assert all(set(r['camera_source_frames'])=={'overview','approach','reference_corner','driver_reference'} and set(r['camera_source_frames'].values())=={r['native_frame']} for r in turn+straight)
    t=check_motion(turn,'ego',(0,10),True);s=check_motion(straight,'ego',(10,0),False)
    check_motion(turn,'other',(-10,0),False);check_motion(straight,'other',(-10,0),False)
    assert t[0]==s[0] and math.dist(t[-1],s[-1])>10
    assert all(a['actor_sources']['other']==b['actor_sources']['other'] for a,b in zip(turn,straight))
    assert all(a['actor_sources']['ego']==b['actor_sources']['ego'] for a,b in zip(turn,straight[:8]))
    return {'frames':1100,'turn_endpoint_m':t[-1],'straight_endpoint_m':s[-1],
            'selected_manifest_sha256':hashlib.sha256((P/'execution-manifest.json').read_bytes()).hexdigest(),
            'selected_case_ids':[selected[suffix]['case_id'] for suffix in ('opposite_left_turn','opposite_straight_comparator')],
            'fixed_fields':['road.xodr','signal_history.jsonl','video_frames.jsonl','road_geometry.json','signal_context.json','stop_context.json','other_route','other_body_history','four_camera_frame_ids'],
            'source_hashes_checked':len(turn_recipe['sources'])+len(straight_recipe['sources'])+2,
            'native_motion_proven':False,'physical_acceptance_claimed':False}

if __name__=='__main__':print(json.dumps(run(),indent=2))
