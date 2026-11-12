"""Source-cited unreviewed traffic-control and marked-lane review frames."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following


def derive(following_source, device_lane_source):
    source=Path(device_lane_source)
    raw=source.read_bytes()
    rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows)<3:raise ValueError('Original signal/lane source incomplete')
    source_sha=sha256(raw).hexdigest()
    previous=None;device=None;lane=None
    for row in rows:
        frame,time_s=row['frame'],row['time_s']
        if previous is not None and (frame!=previous['frame']+1 or abs(time_s-previous['time_s']-.05)>1e-4):
            raise ValueError('Signal/lane source frame join discontinuous')
        if (device is None and previous is not None and
                previous['ego_station_m']<row['stop_station_m']<=row['ego_station_m'] and
                row['native_light_state'].endswith('Red')):
            device=row
        if (lane is None and 700<=row['ego_station_m']<900 and
                row['lateral_center_shift_m']>row['marked_lane_width_m']/2):
            lane=row
        previous=row
    events=derive_following(following_source)
    for category,row in [('device',device),('marked_lane',lane)]:
        if row is None:continue
        events.append({'frame':row['frame'],'category':category,
                       'occurrence_id':'native-candidate-'+category,
                       'source_ref':source.name,'source_sha256':source_sha,
                       'review_status':'unreviewed_native_geometry_candidate',
                       'engineering_trigger':'original red signal/stop station crossing' if category=='device'
                       else 'original body center beyond half marked lane width'})
    events.sort(key=lambda e:(e['frame'],e['occurrence_id']))
    return events


def write_candidates(following_source,device_lane_source,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior event candidate source')
    events=derive(following_source,device_lane_source)
    destination.write_text(json.dumps(events,indent=2)+'\n')
    return events
