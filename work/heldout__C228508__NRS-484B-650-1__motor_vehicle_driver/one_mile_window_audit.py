"""Compare exact following schedules and a separate 20 Hz mile-boundary source proof."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from mile_boundary_audit import audit as audit_boundary


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
    constructions=[read(folder/x['construction']) for x in (base,far)]
    configs=[]
    for construction in constructions:
        configs.append(json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json')))
    a,b=configs
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','required_atoms',
                'source_packets','cameras','closing_encounters','engineering'):
        if a[key]!=b[key]:raise ValueError('Fixed exact construction differs: '+key)
    x=phases(folder/'cases/within_mile/following_construction.py','mile_within_phases')
    y=phases(folder/'cases/beyond_mile/following_construction.py','mile_far_phases')
    first=[p for p in x if 'closing_request' in p.label]
    second=[p for p in y if 'closing_request' in p.label]
    if tuple(vars(first[0]).values())!=tuple(vars(second[0]).values()) or (first[1].start_m,first[1].end_m)!=(1050,1170) or (second[1].start_m,second[1].end_m)!=(1950,2070):
        raise ValueError('Declared second encounter shift differs')
    if (first[1].ego_target_mps,first[1].lead_target_mps)!=(second[1].ego_target_mps,second[1].lead_target_mps):
        raise ValueError('Second encounter speed policy changed')
    boundary=audit_boundary(folder/'cases/beyond_mile/boundary-proof')
    return {'format':'worker-following-mile-comparison-audit','comparison_id':'one_mile_window',
            'case_ids':[base['case_id'],far['case_id']],
            'construction_sha256':[base['construction_sha256'],far['construction_sha256']],
            'schedule_sha256':[digest(folder/'cases/within_mile/following_construction.py'),digest(folder/'cases/beyond_mile/following_construction.py')],
            'second_request_starts_m':[1050,1950],
            'boundary_source_audit':boundary,'auditor_sha256':digest(__file__),
            'scope':'construction and synthetic measurement proof only',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('Retain prior comparison receipt')
    out.write_text(json.dumps(audit(a.folder),indent=2)+'\n')

if __name__=='__main__':main()
