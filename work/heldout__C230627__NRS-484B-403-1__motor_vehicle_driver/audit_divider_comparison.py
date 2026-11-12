"""Independent fixed-condition and mapped-barrier audit for NRS 484B.227."""
import argparse
from copy import deepcopy
import json
from math import hypot
from pathlib import Path

HERE=Path(__file__).resolve().parent


def read(name):return json.loads((HERE/name).read_text())


def audit(base=None,candidate=None,base_diagnostic=None,candidate_diagnostic=None):
    base=deepcopy(base or read('construction.json'))
    candidate=deepcopy(candidate or read('construction-prohibition_227.json'))
    base_diagnostic=deepcopy(base_diagnostic or read('diagnostic-safety_clear.json'))
    candidate_diagnostic=deepcopy(candidate_diagnostic or read('diagnostic-prohibition_227.json'))
    if (not base['case_id'].endswith('__safety_clear') or
            not candidate['case_id'].endswith('__prohibition_227') or
            (base['law_id'],base['cell_id'],base['actor']) !=
            (candidate['law_id'],candidate['cell_id'],candidate['actor'])):
        raise ValueError('227 comparison identity differs')
    left=json.loads(next(item['content'] for item in base['files'] if item['path']=='config.json'))
    right=json.loads(next(item['content'] for item in candidate['files'] if item['path']=='config.json'))
    if (left['engineering'] != right['engineering'] or
            left['cameras'] != right['cameras'] or
            left['required_atoms'] != right['required_atoms']):
        raise ValueError('227 route, participants or cameras differ')
    common=set(base_diagnostic['files']) & set(candidate_diagnostic['files'])
    if (set(candidate_diagnostic['files'])-set(base_diagnostic['files']) !=
            {'u_turn_227_divider.json'} or
            any(base_diagnostic['files'][name] != candidate_diagnostic['files'][name]
                for name in common-{'u_turn_fixture_provenance.json'}) or
            base_diagnostic['videos'] != candidate_diagnostic['videos'] or
            base_diagnostic['graphs'] != candidate_diagnostic['graphs']):
        raise ValueError('227 diagnostic motion, cameras or map source differs')
    packet=json.loads(candidate_diagnostic['files']['u_turn_227_divider.json'])
    report=packet.get('divider_candidate')
    if (not isinstance(report,dict) or report.get('road_id') != 7 or
            (report.get('approach_lane_id'),report.get('opposite_lane_id')) != (-1,1) or
            report.get('divided_highway_legal_judgment') is not None or
            report.get('public_authority_opening_status') is not None or
            report.get('crossover_or_intersection_status') is not None or
            report.get('actual_barrier_crossing_verified') is not False):
        raise ValueError('227 mapped divider or legal status differs')
    a,b=report['approach_xy_m'],report['opposite_xy_m']
    gap=hypot(a[0]-b[0],a[1]-b[1])-sum(report['lane_widths_m'])/2
    boxes=report.get('nearby_divider_boxes')
    if (abs(gap-report['unoccupied_lane_edge_gap_m'])>1e-6 or gap<1 or
            not isinstance(boxes,list) or not boxes or
            any(box.get('label') not in ('GuardRail','Walls','Fences') or
                not box.get('vertices_xy_m') for box in boxes)):
        raise ValueError('227 source median/barrier geometry differs')
    return {'comparison_id':'prohibition_227',
            'case_ids':[base['case_id'],candidate['case_id']],
            'fixed_conditions_verified':True,
            'source_gap_m':gap,'mapped_barrier_count':len(boxes),
            'divided_highway_legal_judgment':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package');args=parser.parse_args()
    if args.package and Path(args.package).resolve()!=HERE:raise ValueError('Wrong 227 package')
    print(json.dumps(audit(),sort_keys=True))


if __name__=='__main__':main()
