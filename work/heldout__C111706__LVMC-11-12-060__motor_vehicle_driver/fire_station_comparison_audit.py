"""Independent fixed-source audit for C111706 station/driveway comparisons."""

import argparse
import hashlib
import json
from pathlib import Path

from fire_station_measurement import measure


COMPARISONS = {
    'entrance_vs_remote': ('front_entrance_turn', 'remote_reference'),
    'approach_vs_remote': ('front_approach_turn', 'remote_reference'),
    'driveway_use_vs_front': ('driveway_use_turn', 'front_entrance_turn'),
}
CAMERAS = ('overview.mkv','approach.mkv',
           'reference_corner.mkv','driver_reference.mkv')
FIXED = ('station_survey.json','other_original.jsonl',
         'video_frames.jsonl','trace.jsonl')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(left, right, comparison_id):
    if comparison_id not in COMPARISONS:
        raise ValueError('Unknown frozen C111706 comparison')
    a,b=Path(left),Path(right)
    expected=COMPARISONS[comparison_id]
    configs=[json.loads((root/'config.json').read_text()) for root in (a,b)]
    if tuple(config['selected_case_id'].split('__')[-1] for config in configs)!=expected:
        raise ValueError('C111706 comparison exact case identities differ')
    for config in configs:
        if (config.get('law_id'),config.get('cell_id'),config.get('actor'),
                config.get('rate_hz'),config.get('duration_s')) != (
                'LVMC-11-12-060','C111706','motor_vehicle_driver',20,12):
            raise ValueError('C111706 comparison scope/capture differs')
    if configs[0].get('cameras')!=configs[1].get('cameras'):
        raise ValueError('Changed fixed four-camera plan')
    for name in FIXED:
        if not (a/name).is_file() or not (b/name).is_file() or (a/name).read_bytes()!=(b/name).read_bytes():
            raise ValueError('Changed or missing fixed original source: '+name)
    for root in (a,b):
        if any(not (root/name).is_file() for name in CAMERAS):
            raise ValueError('Missing named station source camera')
    left_measure,right_measure=measure(a),measure(b)
    if not left_measure['path']['reversal_observed'] or not right_measure['path']['reversal_observed']:
        raise ValueError('Missing original opposite-direction turn contrast')
    left_path,right_path=left_measure['path'],right_measure['path']
    if comparison_id=='entrance_vs_remote':
        if not left_path['body_entrance_overlap_frames'] or right_path['body_entrance_overlap_frames']:
            raise ValueError('Missing measured entrance-front contrast')
    elif comparison_id=='approach_vs_remote':
        if not left_path['body_approach_overlap_frames'] or right_path['body_approach_overlap_frames']:
            raise ValueError('Missing measured station-approach contrast')
    else:
        if not left_path['driveway_frames'] or right_path['driveway_frames']:
            raise ValueError('Missing measured driveway-use contrast')
    return {'format':'fire-station-comparison-audit-v1',
            'comparison_id':comparison_id,
            'case_ids':[config['selected_case_id'] for config in configs],
            'fixed_source_sha256':{name:_sha(a/name) for name in FIXED},
            'left_path':left_path,'right_path':right_path,
            'source_refs':[{'path':str(root/name),'sha256':_sha(root/name)}
                           for root in (a,b)
                           for name in ('subject_original.jsonl',*FIXED,*CAMERAS)],
            'station_identity':'unreviewed','turning_purpose':'unreviewed',
            'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left',required=True)
    parser.add_argument('--right',required=True)
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=audit(args.left,args.right,args.comparison)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':result['comparison_id'],
                      'cases':result['case_ids']}))


if __name__=='__main__':main()
