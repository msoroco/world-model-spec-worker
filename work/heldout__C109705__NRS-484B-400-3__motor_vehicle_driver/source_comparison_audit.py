"""Independent fixed-condition and deliberate-difference turn comparisons."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_source_measurement import measure


BASE='centerline_approach_left_curb_departure'
VARIANTS={'approach_position':('farther_approach_left_curb_departure',
                               ('departure',)),
          'departure_position':('centerline_approach_farther_departure',
                                ('approach','entry'))}


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _case(root):
    config=json.loads((root/'config.json').read_text());case=config['selected_case_id']
    observed=measure(root,case)
    result=json.loads((root/'result.json').read_text())
    if result['measured_values']['turn_original_position']!=observed:
        raise ValueError('Saved turn measurement differs from original source')
    return config,observed,rows(root/'body_footprints.jsonl')


def audit(comparison_id, roots):
    if comparison_id not in VARIANTS or len(roots)!=2:
        raise ValueError('Exact two-case turn comparison required')
    roots=[Path(p) for p in roots]
    base,variant=(_case(root) for root in roots)
    first,second=base[0],variant[0]
    prefix=first['selected_case_id'].rsplit('__',1)[0]+'__'
    if (first['selected_case_id']!=prefix+BASE
            or second['selected_case_id']!=prefix+VARIANTS[comparison_id][0]):
        raise ValueError('Turn comparison case identity differs')
    fixed=('law_id','cell_id','actor','rate_hz','frames','duration_s',
           'required_atoms','source_packets','cameras','target_speed_mps',
           'lookahead_steps','overview_height_delta_m','route_survey')
    if any(first.get(key)!=second.get(key) for key in fixed):
        raise ValueError('Turn comparison fixed configuration differs')
    for name in ('trace.jsonl','video_frames.jsonl','overview.mkv','approach.mkv',
                 'reference_corner.mkv','driver_reference.mkv'):
        if digest(roots[0]/name)!=digest(roots[1]/name):
            raise ValueError('Turn comparison fixed source differs: '+name)
    base_rows,variant_rows=base[2],variant[2]
    if len(base_rows)!=len(variant_rows):
        raise ValueError('Turn comparison original body lengths differ')
    held=VARIANTS[comparison_id][1]
    for a,b in zip(base_rows,variant_rows):
        if a['phase']!=b['phase']:
            raise ValueError('Turn comparison maneuver phase differs')
        if a['phase'] in held and a['body_corners_xy_m']!=b['body_corners_xy_m']:
            raise ValueError('Turn comparison held body phase differs: '+a['phase'])
    if comparison_id=='approach_position':
        measured=[value[1]['approach_nearest_corner_offset_m'] for value in (base,variant)]
    else:
        measured=[value[1]['departure_min_original_corner_to_left_curb_m']
                  for value in (base,variant)]
    return {'format':'worker-turn-comparison-audit','comparison_id':comparison_id,
            'case_ids':[first['selected_case_id'],second['selected_case_id']],
            'source_sha256':[{name:digest(root/name) for name in
                              ('turn_road_geometry.json','body_footprints.jsonl','video_frames.jsonl')}
                             for root in roots],
            'measured_values_m':measured,'difference_realized':measured[1]>measured[0],
            'comparison_complete':measured[1]>measured[0],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--attempts',nargs=2,required=True);args=parser.parse_args()
    print(json.dumps(audit(args.comparison,args.attempts),indent=2))


if __name__=='__main__':main()
