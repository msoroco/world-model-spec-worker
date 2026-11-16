"""Independent CPU comparison of left-side no-yield and right-pass premise diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path
from overtake_geometry import measure


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line]


def audit(reference, right_pass):
    paths = [Path(reference), Path(right_pass)]
    data = [json.loads(path.read_text()) for path in paths]
    sources = [item['files'] for item in data]
    receipts = [json.loads(item['overtake_source_receipt.json']) for item in sources]
    if not receipts[0]['case_id'].endswith('__observed_no_right_yield_holds_speed') or not receipts[1]['case_id'].endswith('__right_pass_permission_premise_no_right_yield'):
        raise ValueError('Right-pass exception exact identity differs')
    fixed = ('trace.jsonl', 'video_frames.jsonl', 'overview-frames.jsonl',
             'approach-frames.jsonl', 'reference_corner-frames.jsonl',
             'driver_reference-frames.jsonl')
    for name in fixed:
        if sources[0][name] != sources[1][name]:
            raise ValueError('Right-pass exception fixed source differs: ' + name)
    if data[0]['videos'] != data[1]['videos'] or data[0]['graphs'] != data[1]['graphs']:
        raise ValueError('Right-pass exception fixed cameras or graphs differ')
    for index in (0, 1):
        for name, expected in receipts[index]['source_sha256'].items():
            if name not in sources[index]:
                if not name.endswith('.mkv'):
                    raise ValueError('Right-pass exception source missing: ' + name)
                continue
            if digest(sources[index][name]) != expected:
                raise ValueError('Right-pass exception original source hash differs: ' + name)
    bodies = [rows(source['overtake_bodies_original.jsonl']) for source in sources]
    if len(bodies[0]) != len(bodies[1]) or len(bodies[0]) < 3:
        raise ValueError('Right-pass exception frame count differs')
    for left, right in zip(*bodies):
        if (left['frame'] != right['frame'] or left['time_s'] != right['time_s'] or
                left['road_forward_xy'] != right['road_forward_xy'] or
                left['ego'] != right['ego'] or
                left['overtaker']['id'] != right['overtaker']['id'] or
                left['overtaker']['speed_mps'] != right['overtaker']['speed_mps']):
            raise ValueError('Right-pass exception fixed actor, speed or frame differs')
        for a, b in zip(left['overtaker']['body_corners_xy_m'], right['overtaker']['body_corners_xy_m']):
            if a[0] != b[0]:
                raise ValueError('Right-pass exception longitudinal pass path differs')
    geometry = [measure(body, receipt['ego_actor_id'], receipt['overtaker_actor_id']) for body, receipt in zip(bodies, receipts)]
    if (geometry[0]['passing_side_at_first_frame'] != 'left' or
            geometry[1]['passing_side_at_first_frame'] != 'right' or
            geometry[0]['first_complete_frame'] != geometry[1]['first_complete_frame'] or
            geometry[0]['max_precompletion_right_shift_m'] != geometry[1]['max_precompletion_right_shift_m'] or
            geometry[0]['max_precompletion_speed_increase_mps'] != geometry[1]['max_precompletion_speed_increase_mps']):
        raise ValueError('Right-pass exception measured side or fixed behavior differs')
    authority = json.loads(sources[1]['right_pass_authority.json'])
    premise = json.loads(sources[1]['right_pass_premise_original.json'])
    survey = json.loads(sources[1]['overtake_site_original.json'])['right_pass_survey']
    if (authority.get('source_url') != 'https://www.leg.state.nv.us/NRs/NRS-484B.html' or
            authority.get('section') != 'NRS 484B.210(1)(b),(2),(3)' or
            premise.get('authority_sha256') != receipts[1]['source_sha256']['right_pass_authority.json'] or
            premise.get('site_sha256') != receipts[1]['source_sha256']['overtake_site_original.json'] or
            premise.get('survey') != survey or
            survey.get('basis') != 'NRS-484B-210-1b' or
            survey.get('moving_lines_each_direction') != 2 or
            survey.get('unobstructed_pavement') is not True or
            survey.get('parked_vehicles_absent') is not True or
            survey.get('pass_path_paved') is not True or
            survey.get('safety_confirmed') is not None or
            survey.get('legal_permission_confirmed') is not None or
            premise.get('safety_confirmed') is not None or
            premise.get('legal_permission_confirmed') is not None):
        raise ValueError('Right-pass exception independent premise differs')
    return {'format':'worker-right-pass-exception-comparison','comparison_id':'right_pass_exception_premise',
            'case_ids':[receipt['case_id'] for receipt in receipts],
            'source_sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
            'frames':len(bodies[0]),'first_complete_frame':geometry[0]['first_complete_frame'],
            'side_change':['left','right'],'fixed_ego_speed_and_right_response':True,
            'authority_section':authority['section'],'survey_basis':survey['basis'],
            'safety_confirmed':None,'legal_permission_confirmed':None,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('reference');parser.add_argument('right_pass');parser.add_argument('--output',required=True)
    args=parser.parse_args();Path(args.output).write_text(json.dumps(audit(args.reference,args.right_pass),indent=2)+'\n')

if __name__=='__main__':main()
