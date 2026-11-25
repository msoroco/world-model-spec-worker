"""Independent source-bound motion cue comparison; no attention inference."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source(short):
    spec=HERE/f'diagnostic-{short}.json'
    recipe=read(HERE/f'fixture-recipe-{short}.json')
    if recipe['generator']['sha256']!=sha(spec):
        raise ValueError('Comparison diagnostic source changed')
    files=read(spec)['files']
    compat=read(HERE/f'compat-{short}-pr/receipt.json')
    saved=read(HERE/f'saved-{short}-processing.json')
    for name in ('native-ego-frames.jsonl','video_frames.jsonl','native-driving-context.json'):
        digest=hashlib.sha256(files[name].encode()).hexdigest()
        if compat['fixture_manifest'][name]!=digest or saved['original_source_hashes'][name]!=digest:
            raise ValueError('Comparison original source binding differs: '+name)
    if not saved['recorded_only'] or not saved['originals_preserved'] or saved['missing_evidence']:
        raise ValueError('Comparison lacks saved-only proof')
    return (json.loads(files['native-driving-context.json']),
            [json.loads(s) for s in files['native-ego-frames.jsonl'].splitlines()])


def audit(reject_fixed_drift=False):
    a,first=source('reference');b,second=source('contrast')
    if reject_fixed_drift:b['camera_sources']['overview']='different-camera.mkv'
    fixed=('camera_sources','driver_attention_to_operation','legal_verdict','source_kind')
    if any(a.get(k)!=b.get(k) for k in fixed):
        raise ValueError('Comparison fixed capture or attention context changed')
    if len(first)!=600 or len(second)!=600:
        raise ValueError('Comparison original source window differs')
    if any(x['native_frame']!=y['native_frame'] or x['time_s']!=y['time_s']
           for x,y in zip(first,second)):
        raise ValueError('Comparison frame/time context changed')
    distance_a=first[-1]['position_m'][0]-first[0]['position_m'][0]
    distance_b=second[-1]['position_m'][0]-second[0]['position_m'][0]
    if distance_a<=75 or distance_b<=75 or distance_a-distance_b<10:
        raise ValueError('Comparison lacks measured throttle/motion cue difference')
    return {'passed':True,'case_ids':[a['case_id'],b['case_id']],
            'source_bound':True,'fixed_camera_and_frame_context':True,
            'measured_progress_m':[distance_a,distance_b],
            'declared_difference':'controller throttle request and motion cue',
            'driver_attention_to_operation':None,
            'scope':'synthetic source/saved-receipt comparison; original operator attention and legal judgment pending'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reject-fixed-drift',action='store_true')
    a=parser.parse_args();print(json.dumps(audit(a.reject_fixed_drift),indent=2))


if __name__=='__main__':main()
