"""Independent fixed-source diagnostic comparison of mixed and repeated device requests."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def audit(folder,core,repeated):
    folder,core,repeated=map(Path,(folder,core,repeated))
    manifest=read(folder/'execution-manifest.json')
    prefix=manifest['assignment_id']+'__'
    entries=[next(x for x in manifest['cases'] if x['case_id']==prefix+name) for name in ('core_device_lane','repeated_device')]
    configs=[]
    for entry in entries:
        construction=read(folder/entry['construction'])
        configs.append(json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms','source_packets','cameras','closing_encounters','engineering','official_control_source'):
        if a[key]!=b[key]:raise ValueError('Fixed construction differs: '+key)
    for name in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl'):
        if digest(core/name)!=digest(repeated/name):raise ValueError('Fixed original diagnostic source differs: '+name)
    counts=[];source_hashes=[]
    for attempt in (core,repeated):
        events=read(attempt/'event_annotations.json')
        device_source=attempt/'device_lane_sources.jsonl'
        source_hashes.append(digest(device_source))
        candidates=[e for e in events if e['category']=='device']
        if any(e.get('source_ref')!=device_source.name or e.get('source_sha256')!=source_hashes[-1] for e in candidates):
            raise ValueError('Uncited device candidate')
        counts.append(len(candidates))
    if counts!=[1,2]:raise ValueError('Device repetition difference absent')
    rows=[json.loads(line) for line in (repeated/'device_lane_sources.jsonl').read_text().splitlines()]
    events=read(repeated/'event_annotations.json')
    seen=set()
    for event in (e for e in events if e['category']=='device'):
        row=next((r for r in rows if r['frame']==event['frame']),None)
        prev=next((r for r in rows if r['frame']==event['frame']-1),None)
        if row is None or prev is None:raise ValueError('Device frame source absent')
        crossed=[x for x in row['signal_observations'] if prev['ego_station_m']<x['stop_station_m']<=row['ego_station_m'] and x['native_light_state'].endswith('Red')]
        if len(crossed)!=1:raise ValueError('Original red crossing absent')
        seen.add(crossed[0]['traffic_light_actor_id'])
    if len(seen)!=2:raise ValueError('Two physical signal identities absent')
    return {'format':'worker-device-repetition-comparison-audit','comparison_id':'different_vs_repeated',
      'case_ids':[x['case_id'] for x in entries], 'construction_sha256':[x['construction_sha256'] for x in entries],
      'fixed_original_sha256':{n:digest(core/n) for n in ('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl')},
      'signal_source_sha256':source_hashes,'device_candidate_counts':counts,'distinct_signal_actor_ids':sorted(seen),
      'auditor_sha256':digest(__file__),'scope':'synthetic source-shaped software comparison only',
      'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--core',required=True);p.add_argument('--repeated',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.folder,a.core,a.repeated),indent=2)+'\n')
if __name__=='__main__':main()
