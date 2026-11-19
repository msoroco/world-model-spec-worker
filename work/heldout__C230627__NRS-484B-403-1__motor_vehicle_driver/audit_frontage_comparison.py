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


def audit_device(base=None, candidate=None, base_diagnostic=None, candidate_diagnostic=None):
    """Compare the mapped device source while holding motion and capture fixed."""
    base = deepcopy(base or read('construction.json'))
    candidate = deepcopy(candidate or read('construction-prohibition_403_2.json'))
    base_diagnostic = deepcopy(base_diagnostic or read('diagnostic-safety_clear.json'))
    candidate_diagnostic = deepcopy(candidate_diagnostic or read('diagnostic-prohibition_403_2.json'))
    if (not base['case_id'].endswith('__safety_clear') or
            not candidate['case_id'].endswith('__prohibition_403_2') or
            (base['law_id'], base['cell_id'], base['actor']) !=
            (candidate['law_id'], candidate['cell_id'], candidate['actor'])):
        raise ValueError('403(2) comparison identity differs')
    base_config = json.loads(next(item['content'] for item in base['files'] if item['path']=='config.json'))
    candidate_config = json.loads(next(item['content'] for item in candidate['files'] if item['path']=='config.json'))
    if (base_config['engineering'] != candidate_config['engineering'] or
            base_config['cameras'] != candidate_config['cameras'] or
            base_config['required_atoms'] != candidate_config['required_atoms']):
        raise ValueError('403(2) route, participants or cameras differ')
    common = set(base_diagnostic['files']) & set(candidate_diagnostic['files'])
    if (set(candidate_diagnostic['files']) - set(base_diagnostic['files']) != {'u_turn_device.json'} or
            set(base_diagnostic['files']) - set(candidate_diagnostic['files']) or
            any(base_diagnostic['files'][name] != candidate_diagnostic['files'][name]
                for name in common - {'u_turn_fixture_provenance.json'}) or
            base_diagnostic['videos'] != candidate_diagnostic['videos'] or
            base_diagnostic['graphs'] != candidate_diagnostic['graphs']):
        raise ValueError('403(2) original motion, source or cameras differ')
    context = json.loads(candidate_diagnostic['files']['u_turn_context.json'])
    source = json.loads(candidate_diagnostic['files']['u_turn_device.json'])
    value = source.get('mapped_no_u_turn_device')
    if (not isinstance(value, dict) or not value.get('landmark_id') or
            value.get('road_id') != context.get('approach_road_id') or
            not isinstance(value.get('source_fields'), dict) or
            any(value.get(key) is not None for key in
                ('official_device_status', 'governing_lane_status', 'pixel_visibility_status'))):
        raise ValueError('403(2) mapped device identity or unresolved status differs')
    label = ' '.join(str(field) for field in value['source_fields'].values()).lower().replace('_', ' ').replace('-', ' ')
    if not any(term in label for term in ('no u turn', 'u turn prohibited', 'u turn forbidden')):
        raise ValueError('403(2) source does not describe a no-U-turn device')
    distance = value.get('distance_to_approach_m')
    if type(distance) not in (int, float) or not 0 <= distance <= 30:
        raise ValueError('403(2) mapped device distance differs')
    return {'comparison_id': 'prohibition_403_2',
            'case_ids': [base['case_id'], candidate['case_id']],
            'fixed_conditions_verified': True,
            'mapped_landmark_id': value['landmark_id'],
            'mapped_distance_to_approach_m': distance,
            'official_device_status': None,
            'governing_lane_status': None,
            'pixel_visibility_status': None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package')
    parser.add_argument('--device', action='store_true')
    args=parser.parse_args()
    if args.package and Path(args.package).resolve()!=HERE:
        raise ValueError('Wrong 403(3) package')
    print(json.dumps(audit_device() if args.device else audit(),sort_keys=True))


if __name__=='__main__':
    main()
