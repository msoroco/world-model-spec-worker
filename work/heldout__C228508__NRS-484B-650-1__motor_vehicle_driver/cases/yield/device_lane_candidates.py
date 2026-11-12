"""Unreviewed source-cited device and cross-traffic yield review frames."""
from hashlib import sha256
import json
from pathlib import Path
from event_candidates import derive as derive_following

def derive(following_source,device_lane_source,yield_source):
    signal=Path(device_lane_source);cross=Path(yield_source)
    signals=[json.loads(x) for x in signal.read_text().splitlines() if x]
    rows=[json.loads(x) for x in cross.read_text().splitlines() if x]
    if len(rows)<3 or len(rows)!=len(signals):raise ValueError('Original signal/yield coverage incomplete')
    signal_sha=sha256(signal.read_bytes()).hexdigest();cross_sha=sha256(cross.read_bytes()).hexdigest()
    prior=None;device=yield_row=None;cross_entered=False;ego_entered=False
    for s,row in zip(signals,rows):
        if (s['frame'],s['time_s'])!=(row['frame'],row['time_s']):raise ValueError('Original yield frame join differs')
        if prior is not None and (s['frame']!=prior['frame']+1 or abs(s['time_s']-prior['time_s']-.05)>1e-4):
            raise ValueError('Original yield time discontinuity')
        if device is None and prior is not None and prior['ego_station_m']<s['stop_station_m']<=s['ego_station_m'] and s['native_light_state'].endswith('Red'):
            device=s
        if row['cross_in_junction'] and not row['ego_in_junction']:
            cross_entered=True
        if row['ego_in_junction'] and not ego_entered:
            ego_entered=True
            if (cross_entered and row['cross_in_junction'] and
                row['ego_signal_state'].endswith('Red') and row['cross_signal_state'].endswith('Green')):
                yield_row=row
        prior=s
    events=derive_following(following_source)
    for category,row,source,h in [('device',device,signal,signal_sha),('yield',yield_row,cross,cross_sha)]:
        if row is None:continue
        events.append({'frame':row['frame'],'category':category,
            'occurrence_id':'native-candidate-'+category,'source_ref':source.name,'source_sha256':h,
            'review_status':'unreviewed_native_geometry_candidate',
            'engineering_trigger':'cross traffic in junction before ego enters' if category=='yield' else 'original red signal/stop station crossing'})
    events.sort(key=lambda e:(e['frame'],e['occurrence_id']))
    return events

def write_candidates(following_source,device_lane_source,yield_source,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior event candidate source')
    events=derive(following_source,device_lane_source,yield_source)
    destination.write_text(json.dumps(events,indent=2)+'\n')
    return events
