"""Independent close-following construction and synthetic body-gap audit."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def audit(folder,core,close):
    folder,core,close=map(Path,(folder,core,close))
    manifest=read(folder/'execution-manifest.json');prefix=manifest['assignment_id']+'__'
    entries=[next(e for e in manifest['cases'] if e['case_id']==prefix+n) for n in ('core_device_lane','too_close')]
    configs=[]
    for e in entries:
        construction=read(folder/e['construction'])
        configs.append(json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms','source_packets','cameras','closing_encounters','official_control_source'):
        if a[key]!=b[key]:raise ValueError('Fixed construction differs: '+key)
    if a['engineering']!={} or b['engineering']!={'lead_spawn_station_m':25,'closing_lead_speed_mps':7}:
        raise ValueError('Lead proximity construction difference absent')
    for n in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl'):
        if digest(core/n)!=digest(close/n):raise ValueError('Fixed original diagnostic source differs: '+n)
    core_events=read(core/'event_annotations.json');close_events=read(close/'event_annotations.json')
    if (not any(e['category']=='marked_lane' for e in core_events) or
        any(e['category']=='marked_lane' for e in close_events) or
        not any(e['category']=='too_close' for e in close_events) or
        not any(e['category']=='device' for e in close_events)):
        raise ValueError('Requested diagnostic review-frame difference absent')
    source=folder/'cases/too_close/headway-boundary-source.jsonl'
    rows=[json.loads(line) for line in source.read_text().splitlines() if line]
    if len(rows)<30:raise ValueError('Headway source too short')
    gaps=[];headways=[]
    for i,r in enumerate(rows):
        if r.get('too_close_legal_judgment') is not None:raise ValueError('Synthetic legal judgment present')
        if i:
            prev=rows[i-1]
            if r['frame']!=prev['frame']+1 or abs(r['time_s']-prev['time_s']-.05)>1e-4:
                raise ValueError('Headway source discontinuous')
            ego_speed=(r['ego_center_xy_m'][0]-prev['ego_center_xy_m'][0])/.05
            lead_speed=(r['lead_center_xy_m'][0]-prev['lead_center_xy_m'][0])/.05
            if abs(ego_speed-r['ego_speed_mps'])>1e-4 or abs(lead_speed-r['lead_speed_mps'])>1e-4:
                raise ValueError('Body speeds and positions differ')
        if abs(r['ego_center_xy_m'][1]-r['lead_center_xy_m'][1])>1e-4:
            raise ValueError('Bodies not in same lane')
        gap=r['lead_center_xy_m'][0]-r['lead_half_length_m']-r['ego_center_xy_m'][0]-r['ego_half_length_m']
        if gap<=0:raise ValueError('Body overlap in synthetic source')
        gaps.append(gap);headways.append(gap/r['ego_speed_mps'])
    if not headways[0]>1.5 or not any(0<h<1.5 for h in headways[1:]):
        raise ValueError('Short-headway review trigger not crossed')
    return {'format':'worker-too-close-comparison-audit','comparison_id':'listed_following',
     'case_ids':[e['case_id'] for e in entries],'construction_sha256':[e['construction_sha256'] for e in entries],
     'fixed_diagnostic_source_sha256':{n:digest(core/n) for n in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl')},
     'headway_source_sha256':digest(source),'initial_headway_s':headways[0],'min_headway_s':min(headways),
     'core_also_has_unreviewed_following_candidates':True,
     'auditor_sha256':digest(__file__),'scope':'synthetic geometry and physical request comparison only; no Native or legal violation claim',
     'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--core',required=True);p.add_argument('--close',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior audit')
    out.write_text(json.dumps(audit(a.folder,a.core,a.close),indent=2)+'\n')
if __name__=='__main__':main()
