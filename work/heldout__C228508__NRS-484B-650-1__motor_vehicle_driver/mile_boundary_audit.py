"""Independent source-hashed 20 Hz path proof for the one-mile measurement edge."""
from hashlib import sha256
import json
from pathlib import Path
from aggressive_window_measurement import MILE_M, measure


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def audit(root):
    root=Path(root)
    trace=root/'driving_trace.jsonl'
    source=root/'following_sources.jsonl'
    near=root/'within-event-annotations.json'
    far=root/'beyond-event-annotations.json'
    rows=[json.loads(line) for line in trace.read_text().splitlines() if line]
    if len(rows)!=2000 or rows[0]['frame']!=1000 or rows[-1]['frame']!=2999:
        raise ValueError('Continuous 100 s original-shaped path missing')
    if digest(source)!=json.loads(near.read_text())[0]['source_sha256'] or digest(source)!=json.loads(far.read_text())[0]['source_sha256']:
        raise ValueError('Event source citation differs')
    a=measure(trace,near,root)
    b=measure(trace,far,root)
    if a['candidate_window'] is None or b['candidate_window'] is not None or b['total_driving_path_m']<=MILE_M:
        raise ValueError('One-mile boundary result differs')
    first=json.loads(far.read_text())
    stations={row['frame']:row['x_m'] for row in rows}
    acts=[item for item in first if item['category']=='too_close']
    act_distance=stations[acts[1]['frame']]-stations[acts[0]['frame']]
    if act_distance<=MILE_M:
        raise ValueError('Requested act separation does not exceed mile')
    return {'format':'worker-mile-boundary-source-audit','scope':'synthetic 20 Hz measurement proof only',
            'trace_sha256':digest(trace),'following_source_sha256':digest(source),
            'within_event_sha256':digest(near),'beyond_event_sha256':digest(far),
            'within_window_path_m':a['candidate_window']['path_m'],
            'beyond_act_separation_m':act_distance,'beyond_candidate_window':b['candidate_window'],
            'auditor_sha256':digest(__file__),'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior boundary receipt')
    out.write_text(json.dumps(audit(a.root),indent=2)+'\n')

if __name__=='__main__':main()
