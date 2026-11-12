"""Unreviewed source-cited device/lane and right-side pass review frames."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following

def derive(following_source,device_lane_source,right_pass_source):
    signal=Path(device_lane_source);passing=Path(right_pass_source)
    signals=[json.loads(x) for x in signal.read_text().splitlines() if x]
    rows=[json.loads(x) for x in passing.read_text().splitlines() if x]
    if len(rows)<3 or len(rows)!=len(signals):raise ValueError('Original signal/pass coverage incomplete')
    signal_sha=sha256(signal.read_bytes()).hexdigest();pass_sha=sha256(passing.read_bytes()).hexdigest()
    device=lane=pass_row=None;prior=None;outside_behind=False
    for s,row in zip(signals,rows):
        if (s['frame'],s['time_s'])!=(row['frame'],row['time_s']):raise ValueError('Original pass frame join differs')
        if prior is not None and (s['frame']!=prior['frame']+1 or abs(s['time_s']-prior['time_s']-.05)>1e-4):
            raise ValueError('Original pass source time discontinuity')
        if device is None and prior is not None and prior['ego_station_m']<s['stop_station_m']<=s['ego_station_m'] and s['native_light_state'].endswith('Red'):
            device=s
        if lane is None and 700<=s['ego_station_m']<900 and s['lateral_center_shift_m']>s['marked_lane_width_m']/2:
            lane=s
        if 300<=row['ego_station_m']<550 and row['right_of_driving_edge_m']>0.3:
            if row['lead_station_m']-row['ego_station_m']>5:outside_behind=True
            if outside_behind and row['ego_station_m']-row['lead_station_m']>5 and pass_row is None:
                pass_row=row
        prior=s
    events=derive_following(following_source)
    for category,row,source,source_sha in [('device',device,signal,signal_sha),('marked_lane',lane,signal,signal_sha),('off_pavement_right_pass',pass_row,passing,pass_sha)]:
        if row is None:continue
        events.append({'frame':row['frame'],'category':category,
            'occurrence_id':'native-candidate-'+category,'source_ref':source.name,
            'source_sha256':source_sha,'review_status':'unreviewed_native_geometry_candidate',
            'engineering_trigger':'right-of-driving-edge while overtaking lead' if category=='off_pavement_right_pass' else 'original device/lane geometry'})
    events.sort(key=lambda e:(e['frame'],e['occurrence_id']))
    return events

def write_candidates(following_source,device_lane_source,right_pass_source,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior event candidate source')
    events=derive(following_source,device_lane_source,right_pass_source)
    destination.write_text(json.dumps(events,indent=2)+'\n')
    return events
