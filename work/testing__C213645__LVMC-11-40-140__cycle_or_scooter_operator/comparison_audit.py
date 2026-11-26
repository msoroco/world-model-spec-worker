"""Independent original-only driveway stop, pedestrian and yield comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AID='testing__C213645__LVMC-11-40-140__cycle_or_scooter_operator'
PAIRS={
    'stop_duty':('stops_pedestrian_no_yield','no_stop_pedestrian'),
    'pedestrian_necessity':('stops_pedestrian_no_yield','stops_no_pedestrian'),
    'yield_when_needed':('stops_pedestrian','stops_pedestrian_no_yield'),
}


def require(ok,message):
    if not ok:raise ValueError(message)


def audit_pair(comparison_id,reports):
    suffixes=PAIRS.get(comparison_id)
    require(suffixes is not None,'unknown driveway comparison')
    case_ids=[AID+'__'+suffix for suffix in suffixes]
    left,right=(reports.get(case_id) for case_id in case_ids)
    for case_id,report in zip(case_ids,(left,right)):
        require(isinstance(report,dict) and report.get('format')=='worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id')==case_id and report.get('frame_count')==900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record',{}).get('source_kind')=='original_native_capture',
                'original accepted report required: '+case_id)
    a,b=left['comparison_record'],right['comparison_record']
    for key in ('fixed_source_sha256','camera_plan','duration_s'):
        require(a.get(key) and a.get(key)==b.get(key),'changed fixed original condition: '+key)
    x,y=a['measurement'],b['measurement']
    require(x.get('frame_count')==y.get('frame_count')==900,'original frame count differs')
    if comparison_id=='stop_duty':
        require((a['requested_stop'],b['requested_stop'])==(True,False) and
                a['requested_pedestrian'] is b['requested_pedestrian'] is True and
                a['requested_yield'] is b['requested_yield'] is False and
                x['last_pre_entry_stop_index'] is not None and y['last_pre_entry_stop_index'] is None,
                'original pre-entry stop contrast absent')
    elif comparison_id=='pedestrian_necessity':
        require(a['requested_stop'] is b['requested_stop'] is True and
                (a['requested_pedestrian'],b['requested_pedestrian'])==(True,False) and
                a['requested_yield'] is b['requested_yield'] is False and
                x['pedestrian_conflict_observed'] is True and
                y['pedestrian_conflict_observed'] is False and x['pedestrian_actor_ids'] and
                not y['pedestrian_actor_ids'],
                'original pedestrian conflict contrast absent')
    else:
        require(a['requested_stop'] is b['requested_stop'] is True and
                a['requested_pedestrian'] is b['requested_pedestrian'] is True and
                (a['requested_yield'],b['requested_yield'])==(True,False) and
                x['operator_yield_observed'] is True and y['operator_yield_observed'] is False,
                'original operator-yield contrast absent')
    return {'format':'c213645-independent-original-comparison-v1',
            'comparison_id':comparison_id,'case_ids':case_ids,
            'fixed_source_sha256':a['fixed_source_sha256'],
            'physical_comparison_passed':True,'legal_verdict_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report-map',type=Path,required=True)
    parser.add_argument('--comparison',choices=tuple(PAIRS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    paths=json.loads(args.report_map.read_text())
    reports={case_id:json.loads(Path(path).read_text()) for case_id,path in paths.items()}
    selected=audit_pair(args.comparison,reports)
    if args.output.exists():raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(selected,indent=2)+'\n')
    print(json.dumps(selected))


if __name__=='__main__':
    main()
