"""Unreviewed original close-following and red-device review-frame candidates."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following

def derive(following_source,device_lane_source):
    source=Path(device_lane_source);raw=source.read_bytes()
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows)<3:raise ValueError('Original signal source incomplete')
    previous=None;device=None
    for row in rows:
        if previous is not None and (row['frame']!=previous['frame']+1 or abs(row['time_s']-previous['time_s']-.05)>1e-4):
            raise ValueError('Original signal frame join discontinuous')
        if device is None and previous is not None and previous['ego_station_m']<row['stop_station_m']<=row['ego_station_m'] and row['native_light_state'].endswith('Red'):
            device=row
        previous=row
    events=derive_following(following_source)
    if device is not None:
        events.append({'frame':device['frame'],'category':'device',
                       'occurrence_id':'native-candidate-device','source_ref':source.name,
                       'source_sha256':sha256(raw).hexdigest(),
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
