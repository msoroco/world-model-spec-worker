"""Derive source-qualified context views from retained original files.

The views expose provenance and unresolved facts. They never turn the authored
entrance outline or synthetic fixture into a verified fire station.
"""
import hashlib
import json
from pathlib import Path

SOURCE_NAMES=('station_entrance_source','highway_side_source','traffic_conflict_source',
              'applicable_law_source','police_direction_source','official_device_source')
AUTHORITY_NAMES=('station_identity','driveway_entrance','highway_boundary','activity_and_directions')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _read(path):
    path=Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: '+path.name)
    return json.loads(path.read_text())

def derive(attempt):
    attempt=Path(attempt)
    context=_read(attempt/'entrance-context.json')
    kind=context.get('source_kind')
    if kind not in ('original_native','synthetic_diagnostic'):
        raise ValueError('Unknown entrance context provenance')
    views={name:{'source_kind':kind,'review_status':'unverified'} for name in SOURCE_NAMES}
    if kind=='synthetic_diagnostic':
        for view in views.values():
            view['diagnostic_only']=True
        return views
    manifest=attempt/'authority/manifest.json'
    if sha(manifest)!=context.get('authority_manifest_sha256'):
        raise ValueError('Original authority manifest hash differs')
    authority=_read(manifest)
    sources=authority.get('sources',{})
    if set(sources)!=set(AUTHORITY_NAMES):
        raise ValueError('Original authority source set differs')
    source_hashes={}
    for name in AUTHORITY_NAMES:
        original=attempt/'authority'/(name+'.source')
        expected=sources[name].get('sha256')
        if not original.is_file() or not expected or sha(original)!=expected:
            raise ValueError('Original authority source missing or changed: '+name)
        if context.get('authority_source_sha256',{}).get(name)!=expected:
            raise ValueError('Entrypoint authority source binding differs: '+name)
        source_hashes[name]=expected
    views['station_entrance_source'].update({'review_status':'retained_authority_record',
        'station_identity_sha256':source_hashes['station_identity'],
        'driveway_entrance_sha256':source_hashes['driveway_entrance'],
        'entrance_geometry':context.get('entrance')})
    views['highway_side_source'].update({'review_status':'retained_authority_record',
        'highway_boundary_sha256':source_hashes['highway_boundary'],
        'road_xodr_sha256':sha(attempt/'road.xodr')})
    traffic_path=attempt/'native-vehicle.jsonl'
    if not traffic_path.is_file():
        raise ValueError('Missing original source: native-vehicle.jsonl')
    count=0
    for line in traffic_path.read_text().splitlines():
        if json.loads(line).get('traffic_conflict_vehicle') is not None:
            count+=1
    views['traffic_conflict_source'].update({'review_status':'raw_actor_samples_retained',
        'native_vehicle_sha256':sha(traffic_path),'actor_sample_count':count})
    directions_path=attempt/'authority/activity_and_directions.source'
    try:
        directions=json.loads(directions_path.read_text())
    except (ValueError,UnicodeDecodeError):
        directions={}
    for name,key in (('applicable_law_source','law'),('police_direction_source','police_officer'),
                     ('official_device_source','official_device')):
        item=directions.get(key)
        if isinstance(item,dict) and {'source_id','issued_by','directed_action','valid_time'}<=set(item):
            views[name].update({'review_status':'source_record_retained',
                'authority_sha256':source_hashes['activity_and_directions'],
                'source_record':item})
        else:
            views[name].update({'review_status':'source_record_missing',
                'authority_sha256':source_hashes['activity_and_directions']})
    return views
