"""Independent fixed-condition and measured-gap comparison for C152976."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from one_way_saved import analyze

PAIRS={'approach_left_edge':('left_edge_reference','approach_shifted_right','approach'),
       'departure_left_edge':('left_edge_reference','departure_shifted_right','departure')}
FIXED=('law_id','cell_id','actor','site_source','vehicle_blueprint_id',
       'rate_hz','duration_s','frames','cameras','required_atoms','source_packets',
       'target_speed_mps','lateral_scale','speed_kp','lookahead_m',
       'overview_height_delta_m')


def _read(root,name):
    return json.loads((Path(root)/name).read_text())


def audit(comparison,first,second):
    if comparison not in PAIRS:raise ValueError('Unknown exact one-way comparison')
    a,b,difference=PAIRS[comparison]
    roots=[Path(first),Path(second)]
    configs=[_read(root,'config.json') for root in roots]
    if tuple(c.get('case_branch') for c in configs)!=(a,b):
        raise ValueError('Wrong exact comparison case identities')
    reports=[analyze(root) for root in roots]
    for key in FIXED:
        if configs[0].get(key)!=configs[1].get(key):
            raise ValueError('Fixed condition differs: '+key)
    sites=[_read(root,'site.json') for root in roots]
    if sites[0]!=sites[1]:raise ValueError('Fixed one-way site/curb source differs')
    values=[r['measurements']['one_way_curb_history']['value'] for r in reports]
    names={'approach':'minimum_approach_gap_m','turn':'minimum_turn_gap_m',
           'departure':'minimum_departure_gap_m'}
    observed={label:[v[key] for v in values] for label,key in names.items()}
    if any(any(v is None for v in pair) for pair in observed.values()):
        raise ValueError('Measured approach, turn or departure gap missing')
    if observed[difference][1] <= observed[difference][0]:
        raise ValueError('Declared lateral body-gap difference unobserved')
    fixed_segment='departure' if difference=='approach' else 'approach'
    if abs(observed[fixed_segment][1]-observed[fixed_segment][0])>1e-6:
        raise ValueError('Measured fixed curb segment differs')
    hashes=[]
    for root,report in zip(roots,reports):
        source=report['measurements']['one_way_curb_history']['sources']
        if any(sha256((root/name).read_bytes()).hexdigest()!=digest for name,digest in source.items()):
            raise ValueError('Comparison original source hash differs')
        hashes.append(source)
    return {'format':'worker-one-way-comparison-audit','comparison_id':comparison,
            'case_ids':[r['case_id'] for r in reports],
            'fixed_conditions_checked':True,'declared_difference_checked':True,
            'measured_segment_gaps_m':observed,'source_hashes':hashes,
            'legal_practicability_judgment':'unresolved',
            'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--first',required=True);parser.add_argument('--second',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise ValueError('Retain prior comparison audit')
    output.write_text(json.dumps(audit(args.comparison,args.first,args.second),indent=2)+'\n')


if __name__=='__main__':main()
