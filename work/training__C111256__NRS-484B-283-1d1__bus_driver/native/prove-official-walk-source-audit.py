"""Exercise official Walk review schema and synthetic production rejection."""
import copy
import hashlib
import json
from pathlib import Path

from official_walk_source_audit import CAMERAS,SOURCES,audit_original,sha,validate_review

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ATTEMPT=ROOT/'.runtime-work/c111256-update015-exact/reference/primary/compatibility-v3'


def reject(call,expected):
    try:call()
    except ValueError as exc:
        if expected not in str(exc):raise
    else:raise AssertionError('Expected rejection: '+expected)


def run():
    mapping=[json.loads(x) for x in (ATTEMPT/'video_frames.jsonl').read_text().splitlines()]
    hashes={name:sha(ATTEMPT/name) for name in SOURCES}
    for frame in mapping:
        frame['source_rgb_sha256']={camera:hashlib.sha256(f'{camera}:{frame["native_frame"]}'.encode()).hexdigest() for camera in CAMERAS}
    review={'format':'c111256-official-walk-review-v1','source_kind':'source_shaped_unit_test',
        'reviewer':'CPU schema test','method':'in-memory source-shaped contract exercise',
        'legal_verdict_claimed':False,'signal_actor_id':620,'source_sha256':hashes,
        'camera_rgb_sequence_sha256':{camera:'a'*64 for camera in CAMERAS},
        'official_signal_verified':False,'governance_verified':False,
        'pedestrian_heading_verified':False,
        'observations':[{'video_frame':i,'native_frame':frame['native_frame'],
          'signal_actor_id':620,'camera':'overview',
          'source_rgb_sha256':frame['source_rgb_sha256']['overview'],
          'display':'Unknown','pedestrian_facing_signal':False,
          'method':'synthetic shape','limitations':'No original pixels or governance'}
          for i,frame in enumerate(mapping)]}
    summary=validate_review(review,mapping,hashes,620,diagnostic=True)
    assert summary['reviewed_frames']==480 and summary['original_walk_verified'] is False
    negatives=[]
    damaged=copy.deepcopy(review);damaged['source_sha256']['road_geometry.json']='0'*64
    reject(lambda:validate_review(damaged,mapping,hashes,620,diagnostic=True),'Walk review identity or source hashes differ');negatives.append('changed source')
    damaged=copy.deepcopy(review);damaged['observations'][10]['source_rgb_sha256']='0'*64
    reject(lambda:validate_review(damaged,mapping,hashes,620,diagnostic=True),'Walk pixel/frame or facing observation differs');negatives.append('changed RGB hash')
    damaged=copy.deepcopy(review);damaged['observations'].pop()
    reject(lambda:validate_review(damaged,mapping,hashes,620,diagnostic=True),'Walk review omits an original frame');negatives.append('missing frame')
    damaged=copy.deepcopy(review);damaged['camera_rgb_sequence_sha256'].pop('approach')
    reject(lambda:validate_review(damaged,mapping,hashes,620,diagnostic=True),'Walk review omits independent camera decode receipts');negatives.append('missing decode')
    reject(lambda:validate_review(review,mapping,hashes,620,diagnostic=False),'Walk review identity or source hashes differ');negatives.append('synthetic review as original')
    reject(lambda:audit_original(ATTEMPT,HERE/'nonexistent-review.json'),
           'Synthetic or unverified Walk construction cannot prove official display');negatives.append('synthetic attempt as original')
    proof={'format':'c111256-official-walk-source-cpu-proof-v1',
           'source_shape_frames':480,'source_hashes':hashes,
           'negative_rejections':negatives,'original_signal_governance_verified':False,
           'original_pixels_verified':False,'physical_acceptance_claimed':False,
           'legal_verdict_claimed':False}
    path=HERE.parent/'update016-official-walk-source-proof.json'
    path.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'source_shape_frames':480,'negative_rejections':len(negatives),
                      'proof_sha256':sha(path),'original_pixels_verified':False}))

if __name__=='__main__':run()
