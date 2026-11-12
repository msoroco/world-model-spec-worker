"""Independent fixed-condition audit for the 403(3) built-frontage candidate."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from u_turn_403_3_frontage import FRONTAGE_M, measure_frontage

HERE = Path(__file__).resolve().parent
BASE = 'safety_clear'
FRONTAGE = 'prohibition_403_3'


def read(name):
    return json.loads((HERE/name).read_text())


def audit(base=None, candidate=None, base_diagnostic=None, candidate_diagnostic=None):
    base = deepcopy(base or read('construction.json'))
    candidate = deepcopy(candidate or read('construction-prohibition_403_3.json'))
    base_diagnostic = deepcopy(base_diagnostic or read('diagnostic-safety_clear.json'))
    candidate_diagnostic = deepcopy(candidate_diagnostic or read('diagnostic-prohibition_403_3.json'))
    if (not base['case_id'].endswith('__'+BASE) or
            not candidate['case_id'].endswith('__'+FRONTAGE) or
            (base['law_id'],base['cell_id'],base['actor']) !=
            (candidate['law_id'],candidate['cell_id'],candidate['actor'])):
        raise ValueError('403(3) comparison identity differs')
    base_config = json.loads(next(item['content'] for item in base['files'] if item['path']=='config.json'))
    candidate_config = json.loads(next(item['content'] for item in candidate['files'] if item['path']=='config.json'))
    if (base_config['engineering'] != candidate_config['engineering'] or
            base_config['cameras'] != candidate_config['cameras'] or
            base_config['required_atoms'] != candidate_config['required_atoms'] or
            candidate_config['case']['recording_description'] != candidate['recording_description']):
        raise ValueError('403(3) route, participants or cameras differ')
    common = set(base_diagnostic['files']) & set(candidate_diagnostic['files'])
    allowed = {'u_turn_fixture_provenance.json'}
    if (set(candidate_diagnostic['files'])-set(base_diagnostic['files']) !=
            {'u_turn_403_3_frontage.json'} or
            any(base_diagnostic['files'][name] != candidate_diagnostic['files'][name]
                for name in common-allowed) or
            base_diagnostic['videos'] != candidate_diagnostic['videos'] or
            base_diagnostic['graphs'] != candidate_diagnostic['graphs']):
        raise ValueError('403(3) diagnostic motion, cameras or map source differs')
    source = json.loads(candidate_diagnostic['files']['u_turn_403_3_frontage.json'])
    report = source.get('built_frontage_candidate')
    if (not isinstance(report,dict) or report.get('site_is_junction') is not False or
            report.get('business_district_legal_judgment') is not None or
            report.get('intersection_exception_status') is not None or
            report.get('divided_highway_opening_exception_status') is not None):
        raise ValueError('403(3) candidate or legal status differs')
    computed = measure_frontage(report['buildings'],report['turn_xy_m'],
                                report['forward_unit_xy'])
    if (computed['combined_built'] != report.get('combined_built') or
            computed['combined_sourced_qualifying_use'] != report.get('combined_sourced_qualifying_use') or
            computed['combined_built']['frontage_m'] < FRONTAGE_M):
        raise ValueError('403(3) source frontage differs')
    return {'comparison_id':'prohibition_403_3',
            'case_ids':[base['case_id'],candidate['case_id']],
            'fixed_conditions_verified':True,
            'candidate_built_frontage_m':computed['combined_built']['frontage_m'],
            'sourced_qualifying_frontage_m':computed['combined_sourced_qualifying_use']['frontage_m'],
            'business_district_legal_judgment':None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package')
    args=parser.parse_args()
    if args.package and Path(args.package).resolve()!=HERE:
        raise ValueError('Wrong 403(3) package')
    print(json.dumps(audit(),sort_keys=True))


if __name__=='__main__':
    main()
