"""Unreviewed source-cited candidates for two distinct governed signal crossings."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following


def derive(following_source, device_lane_source):
    source=Path(device_lane_source)
    raw=source.read_bytes()
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows)<3:raise ValueError('Original signal source incomplete')
    source_sha=sha256(raw).hexdigest()
    prior=None
    found={}
    for row in rows:
        if prior is not None and (row['frame']!=prior['frame']+1 or
            abs(row['time_s']-prior['time_s']-.05)>1e-4):
            raise ValueError('Signal source frame join discontinuous')
        observations=row.get('signal_observations')
        if not isinstance(observations,list) or len(observations)!=2:
            raise ValueError('Two distinct original signal observations required')
        ids=[item['traffic_light_actor_id'] for item in observations]
        if len(set(ids))!=2:raise ValueError('Signal actor IDs not distinct')
        if prior is not None:
            for observation in observations:
                actor=observation['traffic_light_actor_id']
                if (actor not in found and prior['ego_station_m']<observation['stop_station_m']<=row['ego_station_m'] and
                    observation['native_light_state'].endswith('Red')):
                    found[actor]=row
        prior=row
    events=derive_following(following_source)
    for actor,row in found.items():
        events.append({'frame':row['frame'],'category':'device',
                       'occurrence_id':'native-candidate-device-'+str(actor),
                       'source_ref':source.name,'source_sha256':source_sha,
                       'review_status':'unreviewed_native_geometry_candidate',
                       'engineering_trigger':'original red signal/stop station crossing'})
    events.sort(key=lambda e:(e['frame'],e['occurrence_id']))
    return events


def write_candidates(following_source,device_lane_source,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior event candidate source')
    events=derive(following_source,device_lane_source)
    destination.write_text(json.dumps(events,indent=2)+'\n')
    return events
