"""Independent source-bound diagnostic comparison of vehicle and person targets."""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def audit(folder,core,person):
    folder,core,person=map(Path,(folder,core,person))
    manifest=read(folder/'execution-manifest.json');prefix=manifest['assignment_id']+'__'
    entries=[next(e for e in manifest['cases'] if e['case_id']==prefix+n) for n in ('core_device_lane','person_hazard')]
    configs=[]
    for entry in entries:
        construction=read(folder/entry['construction'])
        configs.append(json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms','source_packets','cameras','closing_encounters','engineering','official_control_source'):
        if a[key]!=b[key]:raise ValueError('Fixed construction differs: '+key)
    fixed=('video_frames.jsonl','driving_trace.jsonl','following_sources.jsonl','device_lane_sources.jsonl')
    for n in fixed:
        if digest(core/n)!=digest(person/n):raise ValueError('Fixed original diagnostic source differs: '+n)
    hazards=[]
    for attempt in (core,person):
        ev=[x for x in read(attempt/'event_annotations.json') if x['category']=='hazard']
        if len(ev)!=1:raise ValueError('One hazard candidate required')
        x=ev[0];source=attempt/x['source_ref']
        if digest(source)!=x['source_sha256']:raise ValueError('Hazard original source citation differs')
        hazards.append(x)
    if [x.get('target_type') for x in hazards]!=['vehicle','person']:
        raise ValueError('Hazard target difference absent')
    people=[json.loads(line) for line in (person/'person_sources.jsonl').read_text().splitlines() if line]
    maps=[json.loads(line) for line in (person/'video_frames.jsonl').read_text().splitlines() if line]
    if len(people)!=len(maps):raise ValueError('Person source frame coverage differs')
    for p,m in zip(people,maps):
        if (p['frame'],p['time_s'])!=(m['carla_frame'],m['time_s']):raise ValueError('Person source frame join differs')
        if abs(hypot(*(x-y for x,y in zip(p['ego_xy_m'],p['person_xy_m'])))-p['center_distance_m'])>1e-4:
            raise ValueError('Person source distance differs')
    candidate=next((p for p in people if p['frame']==hazards[1]['frame']),None)
    if candidate is None or candidate['center_distance_m']>=4:raise ValueError('Person proximity source absent')
    return {'format':'worker-hazard-target-comparison-audit','comparison_id':'hazard_target',
     'case_ids':[e['case_id'] for e in entries],'construction_sha256':[e['construction_sha256'] for e in entries],
     'fixed_original_sha256':{n:digest(core/n) for n in fixed},
     'person_source_sha256':digest(person/'person_sources.jsonl'),
     'hazard_target_types':['vehicle','person'],'auditor_sha256':digest(__file__),
     'scope':'synthetic source-shaped software comparison only','physical_acceptance_claimed':False,
     'legal_acceptance_claimed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--core',required=True);p.add_argument('--person',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.folder,a.core,a.person),indent=2)+'\n')
if __name__=='__main__':main()
