"""Recompute the other-occupancy comparison from exact CPU source and receipts."""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(root, name, construction_path, receipt_path, crossing_path, diagnostic_path):
    construction=read(construction_path)
    files={f['path']:f['content'] for f in construction['files']}
    config=json.loads(files['config.json'])
    site=json.loads(files['site.json'])
    diagnostic=read(diagnostic_path)
    receipt=read(receipt_path)
    if receipt.get('passed') is not True or len(receipt.get('checks',[]))!=11:
        raise ValueError(name+': exact compatibility proof missing')
    if receipt.get('construction_sha256')!=sha(construction_path):
        raise ValueError(name+': construction differs from proof')
    if receipt.get('case_id')!=construction['case_id'] or config['selected_case_id']!=construction['case_id']:
        raise ValueError(name+': exact case identity changed')
    if receipt.get('fixture_manifest',{}).get('crossing_history.jsonl')!=sha(crossing_path):
        raise ValueError(name+': retained crossing source differs from proof')
    context_text=diagnostic['files']['junction_context.json']
    if receipt['fixture_manifest'].get('junction_context.json')!=hashlib.sha256(context_text.encode()).hexdigest():
        raise ValueError(name+': context differs from proof')
    context=json.loads(context_text)
    if context['intersection_polygon_xy_m']!=site['crossing_polygon_xy_m']:
        raise ValueError(name+': constructed and source polygons differ')
    polygon=Polygon(site['crossing_polygon_xy_m'])
    if not polygon.is_valid or polygon.area<=0:
        raise ValueError(name+': invalid polygon')
    rows=[json.loads(s) for s in crossing_path.read_text().splitlines() if s.strip()]
    if len(rows)!=900 or config['frames']!=900 or config['rate_hz']!=20 or config['duration_s']!=45:
        raise ValueError(name+': capture duration/rate differs')
    first={'ego':None,'other':None};occupied_approach=[]
    for index,row in enumerate(rows):
        if row['frame']!=rows[0]['frame']+index or abs(row['time_s']-index/20)>1e-9:
            raise ValueError(name+': original frame/time sequence changed')
        inside={}
        for role in ('ego','other'):
            actor=row[role]
            if actor['road_id']!=site['approaches'][role]['road_id'] or len(actor['body_vertices_xy_m'])<4:
                raise ValueError(name+': body or road identity changed')
            inside[role]=MultiPoint(actor['body_vertices_xy_m']).convex_hull.intersects(polygon)
            if inside[role] and first[role] is None:
                first[role]={'frame':row['frame'],'time_s':row['time_s']}
        if inside['other'] and not inside['ego'] and 0<row['ego']['distance_to_intersection_m']<=30:
            occupied_approach.append(row['frame'])
    if any(value is None for value in first.values()):
        raise ValueError(name+': missing body entry')
    examples=receipt.get('measurement_examples',{})
    if examples.get('entry_order',{}).get('value')!=first:
        raise ValueError(name+': independently measured first entry differs')
    if name=='other_inside':
        value=examples.get('other_occupancy_at_ego_approach',{}).get('value')
        if value!={'frames':occupied_approach,'count':len(occupied_approach)}:
            raise ValueError(name+': independently measured occupancy differs')
    return construction,config,site,receipt,first,occupied_approach


def audit(root, inside_source=None):
    a=measure(root,'other_first',root/'construction.json',root/'primary-compat-receipt.json',
              root/'diagnostic-sources/crossing_history.jsonl',root/'diagnostic.json')
    d=root/'cases/yield_sign_other_inside'
    b=measure(root,'other_inside',d/'construction.json',root/'other-inside-compat-receipt.json',
              inside_source or d/'crossing_history.jsonl',d/'diagnostic.json')
    base='testing__C125763__NRS-484B-250-1__motor_vehicle_driver'
    if a[0]['case_id']!=base+'__yield_sign_other_first' or b[0]['case_id']!=base+'__yield_sign_other_inside':
        raise ValueError('Comparison case identity changed')
    if any(a[0][key]!=b[0][key] for key in ('law_id','cell_id','actor','recording_description')) or a[2]!=b[2]:
        raise ValueError('Law, actor, site, or recording contract changed')
    if any(a[1][key]!=b[1][key] for key in ('frames','rate_hz','duration_s','required_atoms')):
        raise ValueError('Capture invariant changed')
    for name in ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
        if a[3]['fixture_manifest'].get(name)!=b[3]['fixture_manifest'].get(name):
            raise ValueError('Camera source changed: '+name)
    if not(a[4]['other']['frame']<a[4]['ego']['frame'] and b[4]['other']['frame']<b[4]['ego']['frame']):
        raise ValueError('Other-first entry condition absent')
    if len(a[5])!=0 or len(b[5])<10:
        raise ValueError('Other-occupancy contrast absent')
    return {'format':'worker-source-other-occupancy-comparison','passed':True,
            'case_ids':[a[0]['case_id'],b[0]['case_id']],
            'other_occupied_ego_approach_frame_counts':{'other_first':len(a[5]),'other_inside':len(b[5])},
            'fixed':['law','cell','actor','site','recording_description','frames','rate','duration','required_atoms','four_diagnostic_camera_streams'],
            'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--inside-source',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.root,args.inside_source),indent=2))
