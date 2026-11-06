"""Independently verify saved joins, controlled pair and tamper rejection."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from measure_u_turn import measure,sha


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run():
    root=HERE/'draft-u-turn-saved'
    saved=[]
    for name in ('straight','u_turn'):
        folder=root/name
        source=folder/'native_samples.jsonl';mapping=folder/'video_frames.jsonl'
        review=folder/'sign-review.json';video=folder/'approach-video-fixture.txt'
        receipt=json.loads((folder/'measurement.json').read_text())
        actual=measure(source,mapping,review,video)
        if actual!=receipt or len(rows(source))!=480 or len(rows(mapping))!=480:
            raise ValueError('Saved receipt or frame count mismatch: '+name)
        if receipt['source_hashes']!={p.name:sha(p) for p in (source,mapping,review,video,folder/'pixel_review.jsonl')}:
            raise ValueError('Source hash mismatch: '+name)
        saved.append((name,rows(source),receipt))
    left,right=saved
    for a,b in zip(left[1],right[1]):
        for key in ('native_frame','time_s','native_road_id'):
            if a[key]!=b[key]:raise ValueError('Controlled input differs: '+key)
    if left[2]['u_turn_within_governed_region_observed'] or not right[2]['u_turn_within_governed_region_observed']:
        raise ValueError('Pair outcome mismatch')
    folder=root/'u_turn'
    source=folder/'native_samples.jsonl';mapping=folder/'video_frames.jsonl'
    review=folder/'sign-review.json';video=folder/'approach-video-fixture.txt'
    original=video.read_bytes()
    try:
        video.write_bytes(original+b'changed')
        try:measure(source,mapping,review,video)
        except ValueError as error:
            if 'source hash' not in str(error):raise
        else:raise AssertionError('Changed video accepted')
    finally:
        video.write_bytes(original)
    return {'passed':True,'frames_per_case':480,'controlled_pair':True,
            'changed_video_rejected':True,'original_sources_restored':sha(video)==right[2]['source_hashes']['approach-video-fixture.txt'],
            'native_executed':False,'accepted':False}


if __name__=='__main__':print(json.dumps(run(),indent=2))
