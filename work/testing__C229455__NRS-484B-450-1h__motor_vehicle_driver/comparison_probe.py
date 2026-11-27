"""Synthetic report-shape proof; never an accepted original comparison."""
from __future__ import annotations
import argparse
import json
from comparison_audit import AID,PAIRS,audit_pair
from safety_zone import CASES,THIRTY_FT_M

def mock_report(case):
    return {'format':'worker-delivery-audit','passed':True,
      'protocol_fixture_checked':False,'case_id':AID+'__'+case.case_id,
      'frame_count':900,'physical_acceptance_claimed':True,
      'comparison_record':{'source_kind':'original_native_capture',
        'fixed_source_sha256':{name:'synthetic-hash' for name in
          ('map','highway','zone','curb','designation','traffic')},
        'camera_plan':['synthetic-four-view'],'duration_s':45,
        'placement':case.placement,'end':case.end,'offset_m':case.offset_m,
        'activity':case.activity,'exception':case.exception,
        'measurement':{'frame_count':900,
          'terminal_signed_end_station_m':case.offset_m if case.placement=='end_band' else -10,
          'terminal_between_zone_and_curb':case.placement=='between',
          'statutory_distance_reference_m':THIRTY_FT_M}}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',choices=tuple(PAIRS),required=True)
    args=parser.parse_args()
    reports={AID+'__'+case.case_id:mock_report(case) for case in CASES}
    accepted=audit_pair(args.comparison,reports)
    if not accepted['physical_comparison_passed'] or accepted['legal_verdict_claimed']:
        raise ValueError('mock comparison structure failed')
    right=AID+'__'+PAIRS[args.comparison][1]
    bad=json.loads(json.dumps(reports))
    bad[right]['comparison_record']['fixed_source_sha256']['zone']='changed-source'
    try:audit_pair(args.comparison,bad)
    except ValueError as error:
        if 'changed fixed original condition' not in str(error):raise
        print('synthetic positive and changed-source negative pass:',args.comparison)
        return
    raise ValueError('changed zone source accepted')
if __name__=='__main__':main()
