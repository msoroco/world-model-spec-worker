"""Independent construction and synthetic right-edge overtaking geometry audit."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def audit(folder,core,passing):
    folder,core,passing=map(Path,(folder,core,passing))
    manifest=read(folder/'execution-manifest.json');prefix=manifest['assignment_id']+'__'
    entries=[next(x for x in manifest['cases'] if x['case_id']==prefix+n) for n in ('core_device_lane','off_pavement_right_pass')]
    configs=[]
    for e in entries:
        construction=read(folder/e['construction'])
        configs.append(json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms','source_packets','cameras','closing_encounters','engineering','official_control_source'):
        if a[key]!=b[key]:raise ValueError('Fixed construction differs: '+key)
    for n in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl','device_lane_sources.jsonl'):
        if digest(core/n)!=digest(passing/n):raise ValueError('Fixed original diagnostic source differs: '+n)
    source=folder/'cases/off_pavement_right_pass/right-pass-boundary-source.jsonl'
    rows=[json.loads(line) for line in source.read_text().splitlines() if line]
    if len(rows)<30:raise ValueError('Right pass source too short')
    initial=rows[0]['lead_station_m']-rows[0]['ego_station_m']
    final=rows[-1]['ego_station_m']-rows[-1]['lead_station_m']
    if initial<=5 or final<=5:raise ValueError('No right-side overtaking order change')
    for i,r in enumerate(rows):
        if r.get('pavement_surface_legal_judgment') is not None or r.get('right_pass_legal_judgment') is not None:
            raise ValueError('Synthetic source asserts legal judgment')
        if i:
            prev=rows[i-1]
            if r['frame']!=prev['frame']+1 or abs(r['time_s']-prev['time_s']-.05)>1e-4:
                raise ValueError('Pass source discontinuous')
            if not .4<=r['ego_station_m']-prev['ego_station_m']<=1.5 or not .1<=r['lead_station_m']-prev['lead_station_m']<=1.0:
                raise ValueError('Pass source motion implausible')
        axis=r['right_axis_xy']
        if abs(hypot(*axis)-1)>1e-4:raise ValueError('Right axis invalid')
        offset=sum((x-y)*a for x,y,a in zip(r['ego_xy_m'],r['road_edge_xy_m'],axis))
        if abs(offset-r['right_of_driving_edge_m'])>1e-4 or offset<=.3:
            raise ValueError('Ego not right of mapped driving edge')
        if abs(r['ego_xy_m'][0]-r['ego_station_m'])>1e-4 or abs(r['lead_xy_m'][0]-r['lead_station_m'])>1e-4:
            raise ValueError('Body positions and stations differ')
    return {'format':'worker-right-pass-comparison-audit','comparison_id':'listed_off_pavement',
      'case_ids':[e['case_id'] for e in entries],'construction_sha256':[e['construction_sha256'] for e in entries],
      'boundary_source_sha256':digest(source),'frames':len(rows),'initial_behind_m':initial,'final_ahead_m':final,
      'auditor_sha256':digest(__file__),'scope':'synthetic geometry and construction request only; pavement material requires original Native pixels',
      'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--core',required=True);p.add_argument('--passing',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior audit')
    out.write_text(json.dumps(audit(a.folder,a.core,a.passing),indent=2)+'\n')
if __name__=='__main__':main()
