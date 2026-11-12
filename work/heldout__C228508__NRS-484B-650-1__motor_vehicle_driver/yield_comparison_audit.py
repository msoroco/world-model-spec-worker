"""Independent fixed-condition and synthetic junction-entry timing audit."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def digest(p): return sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())


def audit(folder, core, yielding):
    folder, core, yielding = map(Path, (folder, core, yielding))
    manifest=read(folder/'execution-manifest.json'); prefix=manifest['assignment_id']+'__'
    entries=[next(x for x in manifest['cases'] if x['case_id']==prefix+n) for n in ('core_device_lane','yield')]
    configs=[]
    for e in entries:
        bundle=read(folder/e['construction'])
        configs.append(json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms','source_packets','cameras','closing_encounters','engineering','official_control_source'):
        if a[key]!=b[key]: raise ValueError('Fixed construction differs: '+key)
    for name in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl'):
        if digest(core/name)!=digest(yielding/name): raise ValueError('Fixed original diagnostic source differs: '+name)
    core_signal=[json.loads(x) for x in (core/'device_lane_sources.jsonl').read_text().splitlines() if x]
    yield_signal=[json.loads(x) for x in (yielding/'device_lane_sources.jsonl').read_text().splitlines() if x]
    if len(core_signal)!=len(yield_signal): raise ValueError('Device source frame coverage differs')
    for x,y in zip(core_signal,yield_signal):
        for key in ('frame','time_s','ego_station_m','stop_station_m','traffic_light_actor_id','opendrive_id','native_light_state','marked_lane_width_m','marked_lane_id','adjacent_lane_id'):
            if x[key]!=y[key]: raise ValueError('Fixed device source differs: '+key)
        if y['lateral_center_shift_m']!=0: raise ValueError('Yield fixture retains marked-lane excursion')
    source=folder/'cases/yield/yield-junction-boundary-source.jsonl'
    rows=[json.loads(x) for x in source.read_text().splitlines() if x]
    if len(rows)<30: raise ValueError('Junction source too short')
    first_cross=next((r['frame'] for r in rows if r['cross_in_junction']),None)
    first_ego=next((r['frame'] for r in rows if r['ego_in_junction']),None)
    if first_cross is None or first_ego is None or first_cross>=first_ego: raise ValueError('Cross traffic did not enter first')
    for i,r in enumerate(rows):
        if (r['yield_legal_judgment'] is not None or r['ego_actor_id']==r['cross_actor_id'] or
            r['ego_road_id']==r['cross_road_id'] or r['ego_signal_actor_id']==r['cross_signal_actor_id'] or
            not r['ego_signal_state'].endswith('Red') or not r['cross_signal_state'].endswith('Green')):
            raise ValueError('Synthetic cross-highway identity/control invalid')
        if i:
            prev=rows[i-1]
            if r['frame']!=prev['frame']+1 or abs(r['time_s']-prev['time_s']-.05)>1e-4 or r['ego_station_m']<=prev['ego_station_m'] or r['cross_station_m']<=prev['cross_station_m']:
                raise ValueError('Synthetic junction motion discontinuous')
    if not any(r['ego_in_junction'] and r['cross_in_junction'] for r in rows): raise ValueError('No junction overlap')
    return {'format':'worker-yield-comparison-audit','comparison_id':'listed_yield','case_ids':[e['case_id'] for e in entries],
        'construction_sha256':[e['construction_sha256'] for e in entries],'boundary_source_sha256':digest(source),
        'frames':len(rows),'cross_entry_frame':first_cross,'ego_entry_frame':first_ego,'auditor_sha256':digest(__file__),
        'scope':'synthetic junction timing and fixed-condition request only; priority, physical encounter and original pixels require Native review',
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--core',required=True);p.add_argument('--yielding',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output)
    if output.exists(): raise ValueError('Retain prior audit')
    output.write_text(json.dumps(audit(a.folder,a.core,a.yielding),indent=2)+'\n')
if __name__=='__main__': main()
