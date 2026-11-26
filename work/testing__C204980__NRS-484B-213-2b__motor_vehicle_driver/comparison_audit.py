"""Independent fixed-condition and deliberate-difference railroad pair audit."""
import argparse
import json
from pathlib import Path

from delivery_audit import inspect_original, audit as audit_delivery

ROOT=Path(__file__).resolve().parent
PLAN=json.loads((ROOT/'case-plan.json').read_text())
COMPARISONS={item['comparison_id']:item for item in PLAN['comparisons']}


def require(ok,reason):
    if not ok:
        raise ValueError(reason)


def normalized_source(attempt,kind):
    value=json.loads((Path(attempt)/('reviewed-'+kind+'.json')).read_text())
    return {key:val for key,val in value.items() if key not in ('case_id','diagnostic_fixture')}


def audit_pair(comparison_id, attempts, *, diagnostic_protocol=False, processing=None,
               pixel_reviews=None):
    comparison=COMPARISONS[comparison_id]
    cases=comparison['case_ids']
    require(set(attempts)==set(cases),'comparison exact case coverage differs')
    for case in cases:
        inspect_original(attempts[case],case,diagnostic_protocol=diagnostic_protocol)
        if not diagnostic_protocol:
            require(processing and pixel_reviews and case in processing and case in pixel_reviews,
                    'independent delivery acceptance missing')
            audit_delivery(attempts[case],case,processing[case],pixel_reviews[case])
    first,second=(Path(attempts[c]) for c in cases)
    for kind in ('railroad','crossing','vehicle'):
        require(normalized_source(first,kind)==normalized_source(second,kind),
                'fixed reviewed '+kind+' source differs')
    highway_a=normalized_source(first,'highway')
    highway_b=normalized_source(second,'highway')
    if comparison_id=='one_way_exception':
        for item in (highway_a,highway_b):
            item.pop('one_way_highway',None)
        require(highway_a==highway_b,'fixed highway status source differs')
    else:
        require(highway_a==highway_b,'fixed highway status source differs')
    observations=[]
    for case in cases:
        report=json.loads((Path(attempts[case])/'analysis-report.json').read_text())
        require(report.get('case_id')==case,'comparison analysis identity differs')
        observations.append(report['observation'])
    a,b=observations
    distances=[a['observed_leading_body_distance_ft'],b['observed_leading_body_distance_ft']]
    if comparison_id=='approach_101_100':
        require(abs(distances[0]-101)<.25 and abs(distances[1]-100)<.25,
                '101/100 foot difference absent')
    elif comparison_id=='approach_100_99':
        require(abs(distances[0]-100)<.25 and abs(distances[1]-99)<.25,
                '100/99 foot difference absent')
    elif comparison_id=='left_vs_right':
        require(abs(distances[0]-distances[1])<.25 and
                a['observed_left_body_extent_at_probe'] is True and
                b['observed_left_body_extent_at_probe'] is False,
                'left/right body difference absent')
    elif comparison_id=='approach_vs_traverse':
        require(a['observed_traversal_at_probe'] is False and
                b['observed_traversal_at_probe'] is True,
                'crossing traversal difference absent')
    elif comparison_id=='one_way_exception':
        require(abs(distances[0]-distances[1])<.25 and
                a['one_way_highway_observed'] is False and
                b['one_way_highway_observed'] is True,
                'one-way status difference absent')
    return {'comparison_id':comparison_id,'case_ids':cases,'passed':True,
            'fixed_reviewed_conditions_checked':True,
            'deliberate_difference_checked':True,
            'diagnostic_protocol':diagnostic_protocol,'legal_judgment':'unresolved'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--comparison',required=True,choices=sorted(COMPARISONS))
    p.add_argument('--attempt',action='append',required=True,
                   help='Exact case ID=absolute attempt path')
    p.add_argument('--processing',action='append',default=[])
    p.add_argument('--pixel-review',action='append',default=[])
    a=p.parse_args()
    def pairs(values):
        return dict(value.split('=',1) for value in values)
    print(json.dumps(audit_pair(a.comparison,pairs(a.attempt),
                                processing=pairs(a.processing),pixel_reviews=pairs(a.pixel_review)),
                     sort_keys=True))


if __name__=='__main__':
    main()
