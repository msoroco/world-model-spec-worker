"""Synthetic Native-shaped intersection completion protocol; no CARLA claim."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ending_road_measurement import measure

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def _sha(path):return sha256(Path(path).read_bytes()).hexdigest()


def run(case_id,kind):
    entry=next((e for e in json.loads((HERE/'execution-manifest.json').read_text())['cases']
                if e['case_id']==case_id),None)
    if entry is None or kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('Unknown exact intersection case or fixture kind')
    recipe=json.loads((ROOT/entry['fixture_recipe']).read_text())
    diagnostic=json.loads((ROOT/recipe['generator']['source']).read_text())['files']
    with TemporaryDirectory(prefix='ending-road-motion-',dir=ROOT/'.runtime-work') as temp:
        base=Path(temp)
        names=('intersection_topology.json','intersection_participants.jsonl','trace.jsonl','video_frames.jsonl')
        for name in names:
            (base/name).write_text(diagnostic[name])
        participants=base/'intersection_participants.jsonl'
        if kind=='missing_evidence':
            participants.unlink()
        elif kind=='incomplete_motion':
            rows=[json.loads(line) for line in participants.read_text().splitlines()]
            for row in rows:
                row['subject_corners']=[[point[0]+1000,point[1]+1000]
                                        for point in row['subject_corners']]
            participants.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))
        sources={name:_sha(base/name) for name in names if (base/name).is_file()}
        observation=None
        if kind=='complete_motion':
            observation=measure(base/'intersection_topology.json',participants)
            status='met' if (observation['subject_entry_frame'] is not None and
                             observation['other_entry_frame'] is not None) else 'not_met'
        else:
            try:measure(base/'intersection_topology.json',participants)
            except ValueError as error:
                expected='Missing required source' if kind=='missing_evidence' else 'Participant never enters'
                if expected not in str(error):raise
            else:raise ValueError('Incomplete intersection source was accepted')
            status='unverified' if kind=='missing_evidence' else 'not_met'
        expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        if status!=expected:raise ValueError('Intersection physical fixture status differs')
        return {'case_id':case_id,'fixture_kind':kind,'fixture_only':True,
            'diagnostic_fixture':True,'actual_native_capture':False,
            'physical_checks':{'maneuver':{'status':status,
                'method':'original Native-shaped body polygon conflict entry for both participants',
                'sources':sources,
                'missing_evidence':['intersection_participants.jsonl'] if kind=='missing_evidence' else []}},
            'maneuver_completed':status=='met',
            'realized_observables':({'subject_entry_frame':observation['subject_entry_frame'],
                                    'other_entry_frame':observation['other_entry_frame']}
                                   if observation else {}),
            'provenance_kind':'native','provenance_note':'Native-shaped synthetic source protocol test only',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',required=True,choices=('complete_motion','incomplete_motion','missing_evidence'))
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=run(args.case,args.kind)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(args.case,args.kind,result['physical_checks']['maneuver']['status'],'synthetic_fixture_only')
