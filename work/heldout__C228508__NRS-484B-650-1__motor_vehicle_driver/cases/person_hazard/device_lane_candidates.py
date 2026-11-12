"""Unreviewed signal/lane and person proximity review frames from original rows."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following

def derive(following_source,device_lane_source,person_source):
    signal=Path(device_lane_source);person=Path(person_source)
    signals=[json.loads(x) for x in signal.read_text().splitlines() if x]
    people=[json.loads(x) for x in person.read_text().splitlines() if x]
    if len(signals)<3 or len(people)!=len(signals):raise ValueError('Original signal/person coverage incomplete')
    signal_sha=sha256(signal.read_bytes()).hexdigest();person_sha=sha256(person.read_bytes()).hexdigest()
    device=lane=hazard=None;previous=None
    person_id=None
    for row,p in zip(signals,people):
        if (row['frame'],row['time_s'])!=(p['frame'],p['time_s']):raise ValueError('Signal/person frame join differs')
        if previous is not None and (row['frame']!=previous['frame']+1 or abs(row['time_s']-previous['time_s']-.05)>1e-4):
            raise ValueError('Original signal/person time discontinuity')
        if person_id is not None and p['person_actor_id']!=person_id:raise ValueError('Person identity changed')
        person_id=p['person_actor_id']
        if device is None and previous is not None and previous['ego_station_m']<row['stop_station_m']<=row['ego_station_m'] and row['native_light_state'].endswith('Red'):
            device=row
        if lane is None and 700<=row['ego_station_m']<900 and row['lateral_center_shift_m']>row['marked_lane_width_m']/2:
            lane=row
        if hazard is None and p['center_distance_m']<4 and 150<=p['ego_station_m']<=300:
            hazard=p
        previous=row
    events=[e for e in derive_following(following_source) if e['category']!='hazard']
    for category,row,source,source_sha in [('device',device,signal,signal_sha),('marked_lane',lane,signal,signal_sha),('hazard',hazard,person,person_sha)]:
        if row is None:continue
        e={'frame':row['frame'],'category':category,'occurrence_id':'native-candidate-'+category,
           'source_ref':source.name,'source_sha256':source_sha,
           'review_status':'unreviewed_native_geometry_candidate'}
        if category=='hazard':e['target_type']='person';e['engineering_trigger']='original person center within 4 m of ego center'
        events.append(e)
    events.sort(key=lambda e:(e['frame'],e['occurrence_id']))
    return events

def write_candidates(following_source,device_lane_source,person_source,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior event candidate source')
    events=derive(following_source,device_lane_source,person_source)
    destination.write_text(json.dumps(events,indent=2)+'\n')
    return events
