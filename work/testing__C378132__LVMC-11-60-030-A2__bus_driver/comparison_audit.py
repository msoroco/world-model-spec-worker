"""Independent A2 pair audit: fixed reviewed conditions and one declared difference."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
FIELDS=('location_kind','loading_purpose','stop_reason','bus_class')
FIXED={'site','designation','route','identity','activity','purpose','circumstances'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_comparison(comparison, reports, *, diagnostic=False):
    ids=comparison['case_ids']
    if len(ids)!=2 or set(reports)!=set(ids):
        raise ValueError('exact comparison cases missing')
    plan=json.loads((ROOT/'case-plan.json').read_text())
    cases={case['case_id']:case for case in plan['cases']}
    observations=[]
    for case_id in ids:
        if case_id not in cases:
            raise ValueError('comparison case absent from exact plan')
        report=reports[case_id]
        if report.get('case_id')!=case_id or report.get('legal_verdict') is not None:
            raise ValueError('wrong analysis case or legal verdict')
        observed=report.get('observation',{})
        if observed.get('diagnostic_only') is not diagnostic:
            raise ValueError('original versus diagnostic source status differs')
        if any(observed.get(key)!=cases[case_id][key] for key in FIELDS):
            raise ValueError('observed A2 loading-stop condition differs from selected probe')
        refs=observed.get('source_refs',{})
        if not FIXED|{'native'}<=set(refs):
            raise ValueError('source-bound comparison observations incomplete')
        observations.append(observed)
    first,second=observations
    changed={key for key in FIELDS if first[key]!=second[key]}
    if len(changed)!=1:
        raise ValueError('comparison requires exactly one observed difference')
    field=next(iter(changed))
    cid=comparison['comparison_id']
    expected='location_kind' if cid in {
        'bus_stop_boundary','bus_stand_location','passenger_loading_zone_location',
        'assigned_route_origin','assigned_route_destination'} else (
        'loading_purpose' if cid in {'passenger_versus_baggage','passenger_versus_cargo'} else (
        'stop_reason' if cid=='emergency_exception' else (
        'bus_class' if cid=='tour_bus_exclusion' else None)))
    if field!=expected:
        raise ValueError('comparison changed a condition other than declared contrast')
    if first.get('observed_duration_s')!=second.get('observed_duration_s'):
        raise ValueError('fixed stopped interval duration changed')
    variable_source={'location_kind':'native','loading_purpose':'purpose',
                     'stop_reason':'circumstances','bus_class':'identity'}[field]
    fixed_sources=FIXED-{variable_source}
    for key in fixed_sources:
        if first['source_refs'][key]['sha256']!=second['source_refs'][key]['sha256']:
            raise ValueError('fixed reviewed A2 source changed: '+key)
    if field!='location_kind' and first['location_kind']!=second['location_kind']:
        raise ValueError('fixed stopped location changed')
    if not comparison.get('deliberate_differences') or not comparison.get('fixed_conditions'):
        raise ValueError('comparison conditions missing')
    return {'format':'worker-bus-loading-comparison-audit','comparison_id':cid,
            'case_ids':ids,'passed':True,'diagnostic_only':diagnostic,
            'fixed_source_sha256':{key:first['source_refs'][key]['sha256'] for key in sorted(fixed_sources)},
            'observed_difference':field,'deliberate_differences':comparison['deliberate_differences'],
            'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--attempts',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads((ROOT/'case-plan.json').read_text())
    comparison=next((x for x in plan['comparisons'] if x['comparison_id']==args.comparison),None)
    if comparison is None:raise ValueError('unknown comparison ID')
    attempts=json.loads(args.attempts.read_text())
    reports={}
    for case_id in comparison['case_ids']:
        folder=Path(attempts[case_id]).resolve()
        path=folder/'analysis-report.json'
        if not path.is_file():raise ValueError('original analysis report missing: '+case_id)
        reports[case_id]=json.loads(path.read_text())
    receipt=audit_comparison(comparison,reports,diagnostic=False)
    if args.output.exists():raise ValueError('retain prior independent comparison receipt')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('original source-bound A2 comparison audited: '+args.comparison)


if __name__=='__main__':main()
