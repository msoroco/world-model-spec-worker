"""Measure original Native rider conflict timing from saved, hashed actor rows."""
import json
from pathlib import Path
from measure_rider_yield import _rows, sha, rectangle, overlap_area

ASSET_IDS={'bicycle':'vehicle.bh.crossbike',
           'electric_bicycle':'vehicle.c10052.electric_bicycle',
           'electric_scooter':'vehicle.c10052.electric_scooter'}


def measure(folder):
    folder=Path(folder)
    samples=folder/'rider_native_samples.jsonl'
    geometry=folder/'rider_geometry.json'
    road=folder/'road_geometry.json'
    manifest_path=folder/'rider-source-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    rider_type=manifest.get('rider_type')
    if manifest.get('source_kind')!='original_native' or manifest.get('accepted') is not False:
        raise ValueError('Original Native source scope missing')
    if rider_type not in ASSET_IDS or manifest.get('rider_blueprint')!=ASSET_IDS[rider_type]:
        raise ValueError('Exact original rider actor class missing')
    if (manifest.get('samples_sha256')!=sha(samples) or
        manifest.get('geometry_sha256')!=sha(geometry) or
        manifest.get('road_geometry_sha256')!=sha(road)):
        raise ValueError('Original Native rider source hash changed')
    geom=json.loads(geometry.read_text())
    survey=json.loads(road.read_text())
    if geom.get('native_map_sha256')!=survey.get('native_map_sha256'):
        raise ValueError('Original Native map survey join differs')
    conflict=rectangle(geom.get('conflict_native_xy_bounds_m'),'conflict bounds')
    facility=rectangle(geom.get('bicycle_facility_native_xy_bounds_m'),'facility bounds')
    if not (facility[0]<=conflict[0]<conflict[2]<=facility[2] and
            facility[1]<=conflict[1]<conflict[3]<=facility[3]):
        raise ValueError('Conflict outside original facility bounds')
    rows=_rows(samples)
    if any(row.get('rider_type')!=rider_type or
           row.get('rider_actor_id')!=manifest.get('rider_actor_id') or
           row.get('rider_blueprint')!=manifest['rider_blueprint'] or
           row.get('rider_native_road_id')!=geom.get('rider_road_id') or
           row.get('rider_native_lane_id')!=geom.get('rider_lane_id') or
           row.get('ego_native_road_id') not in geom.get('ego_road_ids',[])
           for row in rows):
        raise ValueError('Original Native actor or lane identity differs')
    rider=[i for i,row in enumerate(rows) if overlap_area(row['rider_body_xy'],conflict)>.01]
    ego=[i for i,row in enumerate(rows) if overlap_area(row['ego_body_xy'],conflict)>.01]
    if not rider or not ego or rider[0]>=ego[0]:
        raise ValueError('Original rider-first conflict sequence missing')
    simultaneous=len(set(rider)&set(ego))
    return {'format':'c10052-original-rider-conflict-timing-v1',
            'case_id':folder.name,'rider_type':rider_type,
            'rider_actor_id':manifest['rider_actor_id'],
            'rider_blueprint':manifest['rider_blueprint'],
            'first_rider_frame':rows[rider[0]]['native_frame'],
            'last_rider_frame':rows[rider[-1]]['native_frame'],
            'first_ego_frame':rows[ego[0]]['native_frame'],
            'simultaneous_conflict_frames':simultaneous,
            'clearance_s':round((ego[0]-rider[-1])*.05,6),
            'ego_entered_after_rider_cleared':ego[0]>rider[-1],
            'source_sha256':{'samples':sha(samples),'geometry':sha(geometry),
                             'road_survey':sha(road),'manifest':sha(manifest_path)},
            'legal_priority_confirmed':False,'accepted':False}
