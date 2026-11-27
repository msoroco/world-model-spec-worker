"""Build bounded synthetic marked/unmarked source fixtures for CPU compatibility."""
import hashlib
import json
from pathlib import Path
from crosswalk_scene import surface_gap

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ('marked', 'unmarked')

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def body(x, y, radius):
    return [[x-radius,y-radius,0],[x+radius,y-radius,0],
            [x+radius,y+radius,0],[x-radius,y+radius,0]]

def write_case(kind):
    fixture = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    files = fixture['files']
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    if len(trace) != 9:
        raise ValueError('pinned diagnostic frame count changed')
    marking = '<objects><object id="mark-1" type="crosswalk"/></objects>' if kind == 'marked' else '<objects/>'
    files['map.xodr'] = '<OpenDRIVE><road id="main"/><road id="crossing">' + marking + '</road></OpenDRIVE>\n'
    site = {'case_id': ROOT.name + '__' + kind + '_crosswalk', 'cell_id': 'C230221',
            'layout': 'road', 'control': 'crosswalk', 'crosswalk_kind': kind,
            'map_source': {'path': 'map.xodr', 'sha256': digest(files['map.xodr'])},
            'intersecting_road_ids': ['main','crossing'], 'crossing_road_id': 'crossing',
            'intersection_review_source': 'diagnostic Native-shaped junction road IDs',
            'curb_review_source': 'diagnostic Native-shaped opposing sidewalk lane geometry',
            'crossing_polygon_xy_m': [[-1,-4],[1,-4],[1,4],[-1,4]],
            'near_curb_polygon_xy_m': [[-2,-7],[2,-7],[2,-4.1],[-2,-4.1]],
            'far_curb_polygon_xy_m': [[-2,4.1],[2,4.1],[2,7],[-2,7]],
            'pedestrian_route_xy_m': [[0,-5],[0,0],[0,5]],
            'ego_route_xy_m': [[-30,0],[20,0]],
            'marking_object_id': 'mark-1' if kind == 'marked' else None,
            'diagnostic_only': True}
    files['crosswalk-site.json'] = json.dumps(site, sort_keys=True) + '\n'
    history=[]
    for i, frame in enumerate(trace):
        ego,ped=body(-12+i,0,0.5),body(0,-5+1.25*i,0.2)
        event={'source':'original_driver_input','observed':True,
               'kind':'diagnostic_scripted_input'} if i>=2 else None
        brake=int(i>=2)
        history.append({'frame':frame['frame'],'time_s':frame['time_s'],
                        'ego_body_vertices_m':ego,'pedestrian_body_vertices_m':ped,
                        'ego_speed_mps':4,'ego_brake':brake,
                        'pedestrian_class_source':'diagnostic/actor-blueprint',
                        'driver_control_source':'diagnostic/scripted-driver-input',
                        'pedestrian_class':'pedestrian','ego_class':'motor_vehicle',
                        'driver_observation_event':event,
                        'surface_gap_m':surface_gap(ego,ped),'contact_event':False})
    files['encounter-history.jsonl']=''.join(json.dumps(row,sort_keys=True)+'\n' for row in history)
    names=('map.xodr','crosswalk-site.json','encounter-history.jsonl','video_frames.jsonl')
    files['acquisition.json']=json.dumps({name:{'kind':'original_native','sha256':digest(files[name])}
                                           for name in names},sort_keys=True)+'\n'
    files['fixture-provenance.json']=json.dumps({'scope':'CPU synthetic source text only',
        'case_specific_sources':list(names),'physical_acceptance_claimed':False,
        'human_observation_claimed':False})+'\n'
    path=ROOT/('diagnostic-'+kind+'_crosswalk.json')
    path.write_text(json.dumps(fixture,ensure_ascii=False,separators=(',',':'))+'\n')
    assignment=ROOT/'assignment.json'
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':str(assignment.relative_to(REPO)),
                        'sha256':hashlib.sha256(assignment.read_bytes()).hexdigest()}],
            'generator':{'source':str(path.relative_to(REPO)),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT/('diagnostic-'+kind+'_crosswalk-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')

if __name__=='__main__':
    for kind in KINDS:
        write_case(kind)
