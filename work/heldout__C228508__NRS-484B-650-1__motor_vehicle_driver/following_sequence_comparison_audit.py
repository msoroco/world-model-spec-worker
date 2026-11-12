"""Source-hashed diagnostic comparison for requested event order; no Native claim."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from window_audit import audit as audit_window


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def audit(base, reverse):
    base, reverse=Path(base),Path(reverse)
    a,b=(read(root/'config.json') for root in (base,reverse))
    prefix='heldout__C228508__NRS-484B-650-1__motor_vehicle_driver__'
    if (a['selected_case_id'],b['selected_case_id'])!=(prefix+'repeated_following',prefix+'reverse_sequence'):
        raise ValueError('Wrong sequence comparison cases')
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms',
                'source_packets','cameras','closing_encounters'):
        if a[key]!=b[key]:raise ValueError('Fixed construction differs: '+key)
    if a['engineering'] or b['engineering']!={'early_speed_cap_mps':18,'speed_phase_start_station_m':660}:
        raise ValueError('Late speed request missing or confounded')
    for name in ('video_frames.jsonl','driving_trace.jsonl','trace.jsonl'):
        if digest(base/name)!=digest(reverse/name):raise ValueError('Fixed original diagnostic source differs: '+name)
    x,y=rows(base/'following_sources.jsonl'),rows(reverse/'following_sources.jsonl')
    if len(x)!=len(y) or not x:raise ValueError('Body source row count differs')
    for left,right in zip(x,y):
        if (left['frame'],left['time_s'],left['ego']['position_m'],left['lead'])!=(right['frame'],right['time_s'],right['ego']['position_m'],right['lead']):
            raise ValueError('Fixed body position/lead source differs')
    if not all(row['ego']['speed_mps']==18 for row in y[:4]) or not all(row['ego']['speed_mps']==24 for row in y[4:]):
        raise ValueError('Late speed body source absent')
    cats=[]
    for root in (base,reverse):
        events=read(root/'event_annotations.json')
        cats.append([item['category'] for item in sorted(events,key=lambda item:item['frame'])])
        source=digest(root/'following_sources.jsonl')
        if any(item['source_sha256']!=source for item in events):
            raise ValueError('Stale source citation')
    if cats!=[['speed','too_close','too_close','hazard'],['too_close','too_close','hazard','speed']]:
        raise ValueError('Source-cited event order differs')
    windows=[audit_window(root,root/'analysis-report.json')['candidate_window'] for root in (base,reverse)]
    if any(window is None for window in windows):raise ValueError('Measured window missing')
    return {'format':'worker-following-sequence-comparison-audit','comparison_id':'following_any_sequence',
            'case_ids':[a['selected_case_id'],b['selected_case_id']],
            'fixed_source_sha256':{name:digest(base/name) for name in ('video_frames.jsonl','driving_trace.jsonl','trace.jsonl')},
            'body_source_sha256':[digest(root/'following_sources.jsonl') for root in (base,reverse)],
            'event_source_sha256':[digest(root/'event_annotations.json') for root in (base,reverse)],
            'candidate_window_frames':[[w['start_frame'],w['end_frame']] for w in windows],
            'auditor_sha256':digest(__file__),'scope':'synthetic software diagnostic only',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--reverse',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.base,a.reverse),indent=2)+'\n')

if __name__=='__main__':main()
