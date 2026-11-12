"""Independent fixed-condition and mapped school-sign comparison audit."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from u_turn_finalizer import measure_school_zone_candidate

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text())


def audit(base=None, candidate=None, base_diagnostic=None,
          candidate_diagnostic=None):
    base = deepcopy(base or read('construction.json'))
    candidate = deepcopy(candidate or read('construction-prohibition_363.json'))
    base_diagnostic = deepcopy(base_diagnostic or read('diagnostic-safety_clear.json'))
    candidate_diagnostic = deepcopy(candidate_diagnostic or read('diagnostic-prohibition_363.json'))
    if (not base['case_id'].endswith('__safety_clear') or
            not candidate['case_id'].endswith('__prohibition_363') or
            (base['law_id'],base['cell_id'],base['actor']) !=
            (candidate['law_id'],candidate['cell_id'],candidate['actor'])):
        raise ValueError('363 comparison identity differs')
    left = json.loads(next(item['content'] for item in base['files']
                           if item['path']=='config.json'))
    right = json.loads(next(item['content'] for item in candidate['files']
                            if item['path']=='config.json'))
    if (left['engineering'] != right['engineering'] or
            left['cameras'] != right['cameras'] or
            left['required_atoms'] != right['required_atoms']):
        raise ValueError('363 route, participants or cameras differ')
    common = set(base_diagnostic['files']) & set(candidate_diagnostic['files'])
    if (set(candidate_diagnostic['files'])-set(base_diagnostic['files']) !=
            {'u_turn_363_school.json'} or
            any(base_diagnostic['files'][name] != candidate_diagnostic['files'][name]
                for name in common-{'u_turn_fixture_provenance.json'}) or
            base_diagnostic['videos'] != candidate_diagnostic['videos'] or
            base_diagnostic['graphs'] != candidate_diagnostic['graphs']):
        raise ValueError('363 diagnostic motion, cameras or map source differs')
    packet = json.loads(candidate_diagnostic['files']['u_turn_363_school.json'])
    school = packet.get('school_zone_candidate')
    context = json.loads(candidate_diagnostic['files']['u_turn_context.json'])
    if not isinstance(school, dict) or not school.get('matching_landmarks'):
        raise ValueError('363 mapped school-zone source missing')
    if (school.get('road_id') != context.get('approach_road_id') or
            school.get('approach_lane_id') != context.get('approach_lane_id') or
            any(school.get(key) is not None for key in (
                'official_zone_designation','children_present','school_in_session',
                'governing_body_exempt_period','operational_beacon',
                'pupils_in_class','yellow_beacon_lights_flashing',
                'sign_speed_limit_in_effect','legal_prohibition_applicable'))):
        raise ValueError('363 candidate identity or legal alternatives differ')
    return {'comparison_id':'prohibition_363',
            'case_ids':[base['case_id'],candidate['case_id']],
            'fixed_conditions_verified':True,
            'mapped_school_landmark_count':len(school['matching_landmarks']),
            'legal_prohibition_applicable':None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package')
    args = parser.parse_args()
    if args.package and Path(args.package).resolve() != HERE:
        raise ValueError('Wrong 363 package')
    print(json.dumps(audit(),sort_keys=True))


if __name__ == '__main__':
    main()
