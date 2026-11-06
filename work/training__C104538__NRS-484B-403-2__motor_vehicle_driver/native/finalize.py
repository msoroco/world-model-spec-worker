"""Saved signed U-turn analysis; proposed CPU entrypoint, no legal verdict."""
import argparse
import json
from pathlib import Path

from measure_u_turn import measure


def measure_signed_u_turn(attempt):
    root=Path(attempt)
    return measure(root/'native_samples.jsonl',root/'video_frames.jsonl',
                   root/'sign-review.json',root/'approach.mkv')


def finalize(attempt,output):
    root=Path(attempt)
    if not (root/'native_samples.jsonl').is_file():
        raise ValueError('Missing required source: native_samples.jsonl')
    value=measure_signed_u_turn(root)
    report={'format':'c104538-signed-u-turn-saved-analysis-v1',
            'measurements':{'signed_u_turn':{'method':'measure_signed_u_turn',
                'value':value,'sources':{
                    name:value['source_hashes'][Path(name).name] for name in
                    ('native_samples.jsonl','video_frames.jsonl','sign-review.json','approach.mkv')}}},
            'native_executed':False,'accepted':False,'legal_verdict_claimed':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)
