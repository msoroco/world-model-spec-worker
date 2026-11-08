"""Source-bound heavy-vehicle sidewalk/entrance geometry; no legal conclusion."""
import hashlib
import json
import math
from pathlib import Path
from measure_saved import measure as measure_saved, records


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError('Polygon needs three vertices')
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
            raise ValueError('Polygon coordinate invalid')
        points.append(tuple(float(v) for v in point))
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1]))/2
    if abs(area) < .01 or len(set(points)) != len(points):
        raise ValueError('Polygon degenerate')
    return points


def orient(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def inside(point, poly):
    x,y=point
    return any(abs(orient(a,b,point))<1e-8 and min(a[0],b[0])<=x<=max(a[0],b[0]) and min(a[1],b[1])<=y<=max(a[1],b[1]) for a,b in zip(poly,poly[1:]+poly[:1])) or sum(((a[1]>y)!=(b[1]>y)) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0] for a,b in zip(poly,poly[1:]+poly[:1]))%2==1


def intersects(a,b):
    if any(inside(p,b) for p in a) or any(inside(p,a) for p in b):
        return True
    for u,v in zip(a,a[1:]+a[:1]):
        for p,q in zip(b,b[1:]+b[:1]):
            if orient(u,v,p)*orient(u,v,q)<0 and orient(p,q,u)*orient(p,q,v)<0:
                return True
    return False


def transform(points, matrix):
    if not isinstance(matrix,list) or len(matrix)!=2 or any(not isinstance(r,list) or len(r)!=3 for r in matrix) or any(type(v) not in (int,float) or not math.isfinite(v) for r in matrix for v in r):
        raise ValueError('Affine transform invalid')
    a,b=matrix
    if abs(a[0]*b[1]-a[1]*b[0])<1e-9:
        raise ValueError('Affine transform singular')
    return [(a[0]*x+a[1]*y+a[2],b[0]*x+b[1]*y+b[2]) for x,y in points]


def surveyed_polygons(survey):
    if survey.get('type') != 'FeatureCollection' or not isinstance(survey.get('features'), list):
        raise ValueError('Survey GeoJSON collection absent')
    features={}
    for feature in survey['features']:
        if not isinstance(feature,dict) or not isinstance(feature.get('id'),str) or feature['id'] in features:
            raise ValueError('Survey feature identity differs')
        geometry=feature.get('geometry')
        if not isinstance(geometry,dict) or geometry.get('type')!='Polygon' or not isinstance(geometry.get('coordinates'),list) or len(geometry['coordinates'])!=1:
            raise ValueError('Survey feature geometry unsupported')
        ring=geometry['coordinates'][0]
        if not isinstance(ring,list) or len(ring)<4 or ring[0]!=ring[-1]:
            raise ValueError('Survey feature ring unclosed')
        polygon(ring[:-1])
        features[feature['id']]=ring[:-1]
    if 'city_boundary' not in features or 'sidewalk' not in features:
        raise ValueError('Survey City or sidewalk feature absent')
    entrances=[]
    for identity,points in features.items():
        if identity in ('city_boundary','sidewalk'):
            continue
        kind,separator,name=identity.partition(':')
        if separator!=':' or kind not in ('driveway','alley') or not name:
            raise ValueError('Unclassified survey feature')
        entrances.append({'id':identity,'kind':kind,'polygon':points})
    return {'city_boundary_polygon':features['city_boundary'],
            'sidewalk_polygon':features['sidewalk'],
            'entrance_polygons':sorted(entrances,key=lambda item:item['id'])}


def measure(folder, context_path):
    folder,context_path=Path(folder),Path(context_path)
    saved=measure_saved(folder)
    packet=json.loads(context_path.read_text())
    if packet.get('format')!='c422978-heavy-spatial-context-v1' or packet.get('law_id')!='NRS-484B-117-1' or packet.get('map_readback_sha256')!=sha(folder/'native-map-readback.json'):
        raise ValueError('Spatial context identity or map binding differs')
    if packet.get('authority_kind') not in ('synthetic_cpu','unreviewed_survey') or packet.get('city_authority_reviewed') is not False or packet.get('entrance_authority_reviewed') is not False:
        raise ValueError('Spatial authority scope differs')
    provenance=packet.get('source_provenance')
    survey_path=folder/'city-survey-source.geojson'
    calibration_path=folder/'city-calibration.json'
    if not survey_path.is_file() or not calibration_path.is_file():
        raise ValueError('Survey or calibration source absent')
    if not isinstance(provenance,dict) or provenance.get('source_sha256')!=sha(survey_path) or provenance.get('calibration_sha256')!=sha(calibration_path) or not isinstance(provenance.get('crs'),str) or not provenance['crs'] or not isinstance(provenance.get('calibration_source'),str) or not provenance['calibration_source']:
        raise ValueError('Spatial provenance absent')
    survey=json.loads(survey_path.read_text())
    calibration=json.loads(calibration_path.read_text())
    if (survey.get('source_crs')!=provenance['crs'] or calibration.get('source_crs')!=provenance['crs'] or
            calibration.get('native_to_context_affine')!=packet.get('native_to_context_affine') or
            calibration.get('map_readback_sha256')!=sha(folder/'native-map-readback.json') or
            calibration.get('calibration_source')!=provenance['calibration_source']):
        raise ValueError('Survey CRS or calibration differs')
    if survey.get('source_kind')!=('synthetic_cpu' if packet['authority_kind']=='synthetic_cpu' else 'surveyed_city_source'):
        raise ValueError('Survey provenance differs')
    geometry=surveyed_polygons(survey)
    if any(geometry[key]!=packet.get(key) for key in geometry):
        raise ValueError('Survey geometry differs')
    affine=packet.get('native_to_context_affine')
    transform([(0,0)],affine)
    sidewalk=polygon(packet.get('sidewalk_polygon'))
    city=polygon(packet.get('city_boundary_polygon'))
    entrances=packet.get('entrance_polygons')
    if not isinstance(entrances,list):
        raise ValueError('Entrance inventory absent')
    seen=set()
    parsed=[]
    for item in entrances:
        if not isinstance(item,dict) or item.get('kind') not in ('driveway','alley') or not isinstance(item.get('id'),str) or not item['id'] or item['id'] in seen:
            raise ValueError('Entrance identity invalid')
        seen.add(item['id'])
        parsed.append((item['id'],polygon(item.get('polygon'))))
    rows=records(folder/'native-observed.jsonl')
    sidewalk_frames=[]; city_frames=[]; entrance_frames=[]; outside=[]
    entrance_ids=set()
    for index,row in enumerate(rows):
        if row['speed_mps']<=.1:
            continue
        body=transform([tuple(point) for point in row['body_native_xy_m']],affine)
        # Use the convex hull so the source corner order cannot omit edge crossings.
        body=sorted(set(body))
        if len(body)!=4:
            raise ValueError('Body transform collapsed')
        lower=[]; upper=[]
        for p in body:
            while len(lower)>=2 and orient(lower[-2],lower[-1],p)<=0: lower.pop()
            lower.append(p)
        for p in reversed(body):
            while len(upper)>=2 and orient(upper[-2],upper[-1],p)<=0: upper.pop()
            upper.append(p)
        body=lower[:-1]+upper[:-1]
        on_sidewalk=intersects(body,sidewalk)
        in_city=intersects(body,city)
        touched=[identity for identity,poly in parsed if intersects(body,poly)]
        if on_sidewalk: sidewalk_frames.append(index)
        if in_city: city_frames.append(index)
        if touched: entrance_frames.append(index); entrance_ids.update(touched)
        if on_sidewalk and in_city and not touched: outside.append(index)
    return {'format':'c422978-heavy-spatial-measurement-v1','source_kind':saved['source_kind'],
            'authority_kind':packet['authority_kind'],'frames':480,
            'moving_sidewalk_intersection_frames':len(sidewalk_frames),
            'moving_city_intersection_frames':len(city_frames),
            'moving_entrance_intersection_frames':len(entrance_frames),
            'moving_city_sidewalk_outside_entrance_frames':len(outside),
            'first_outside_entrance_frame':outside[0] if outside else None,
            'touched_entrance_ids':sorted(entrance_ids),
            'city_authority_reviewed':False,'entrance_authority_reviewed':False,
            'legal_verdict':None,
            'source_hashes':{**saved['source_hashes'],'city-context.json':sha(context_path),
                             'city-survey-source.geojson':sha(survey_path),
                             'city-calibration.json':sha(calibration_path)}}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--context',required=True)
    args=p.parse_args();print(json.dumps(measure(args.attempt,args.context),indent=2))
