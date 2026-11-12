"""Compare exact following schedules and a separate 20 Hz mile-boundary source proof."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from mile_boundary_audit import audit as audit_boundary
from aggressive_window_measurement import MILE_M, measure


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def phases(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name]=module
    spec.loader.exec_module(module)
    module.validate_schedule()
    return module.PHASES


def audit(folder):
    folder=Path(folder)
    manifest=read(folder/'execution-manifest.json')
    prefix=manifest['assignment_id']+'__'
    base=next(x for x in manifest['cases'] if x['case_id']==prefix+'within_mile')
    far=next(x for x in manifest['cases'] if x['case_id']==prefix+'beyond_mile')
    exact=next(x for x in manifest['cases'] if x['case_id']==prefix+'at_mile')
    constructions=[read(folder/x['construction']) for x in (base,exact,far)]
    configs=[]
    for construction in constructions:
        configs.append(json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json')))
    a,b,c=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms',
                'source_packets','cameras','closing_encounters','engineering'):
        if a[key]!=b[key] or a[key]!=c[key]:raise ValueError('Fixed exact construction differs: '+key)
    x=phases(folder/'cases/within_mile/following_construction.py','mile_within_phases')
    y=phases(folder/'cases/beyond_mile/following_construction.py','mile_far_phases')
    z=phases(folder/'cases/at_mile/following_construction.py','mile_exact_phases')
    first=[p for p in x if 'closing_request' in p.label]
    second=[p for p in y if 'closing_request' in p.label]
    middle=[p for p in z if 'closing_request' in p.label]
    if tuple(vars(first[0]).values())!=tuple(vars(second[0]).values()) or (first[1].start_m,first[1].end_m)!=(1050,1170) or (second[1].start_m,second[1].end_m)!=(1950,2070):
        raise ValueError('Declared second encounter shift differs')
    if (first[1].ego_target_mps,first[1].lead_target_mps)!=(second[1].ego_target_mps,second[1].lead_target_mps):
        raise ValueError('Second encounter speed policy changed')
    if (tuple(vars(first[0]).values())!=tuple(vars(middle[0]).values()) or
            abs(middle[1].end_m-middle[0].start_m-MILE_M)>1e-6 or
            (middle[1].start_m,middle[1].end_m)!=(1669.344,1789.344) or
            (middle[1].ego_target_mps,middle[1].lead_target_mps)!=(first[1].ego_target_mps,first[1].lead_target_mps)):
        raise ValueError('Exactly-at-mile schedule differs')
    boundary=audit_boundary(folder/'cases/beyond_mile/boundary-proof')
    root=folder/'cases/at_mile/boundary-proof'
    rows=[json.loads(line) for line in (root/'driving_trace.jsonl').read_text().splitlines() if line]
    events=read(root/'at-event-annotations.json')
    if (len(rows)!=2000 or rows[0]['frame']!=1000 or rows[-1]['frame']!=2999 or
            any(e['source_sha256']!=digest(root/'following_sources.jsonl') for e in events)):
        raise ValueError('Exactly-at-mile source continuity or citation differs')
    at=measure(root/'driving_trace.jsonl',root/'at-event-annotations.json',root)
    if at['candidate_window'] is None or abs(at['candidate_window']['path_m']-MILE_M)>1e-6:
        raise ValueError('Exactly-at-mile synthetic path differs')
    return {'format':'worker-following-mile-comparison-audit','comparison_id':'one_mile_window',
            'case_ids':[base['case_id'],exact['case_id'],far['case_id']],
            'construction_sha256':[base['construction_sha256'],exact['construction_sha256'],far['construction_sha256']],
            'schedule_sha256':[digest(folder/'cases/within_mile/following_construction.py'),digest(folder/'cases/at_mile/following_construction.py'),digest(folder/'cases/beyond_mile/following_construction.py')],
            'second_request_starts_m':[1050,1669.344,1950],
            'at_boundary_path_m':at['candidate_window']['path_m'],
            'at_boundary_trace_sha256':digest(root/'driving_trace.jsonl'),
            'at_boundary_events_sha256':digest(root/'at-event-annotations.json'),
            'boundary_source_audit':boundary,'auditor_sha256':digest(__file__),
            'scope':'construction and synthetic measurement proof only',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.folder),indent=2)+'\n')

if __name__=='__main__':main()
