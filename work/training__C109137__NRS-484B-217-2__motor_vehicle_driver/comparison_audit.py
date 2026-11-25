"""Independent exact-case source comparison across selected primary and fallback pairs."""
import argparse
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
CROSSING = runpy.run_path(str(HERE / 'prove-selected-crossing-pair.py'))
TRAFFIC = runpy.run_path(str(HERE / 'native/zone/audit_traffic_sources.py'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def source(prefix, traffic):
    fixture = HERE / (prefix + '-fixture')
    raw, frames, review_path = (fixture / name for name in
                                ('native-raw-actors.jsonl', 'video_frames.jsonl', 'review.json'))
    review = read(review_path)
    if review['raw_sha256'] != sha(raw) or review['video_frames_sha256'] != sha(frames):
        raise ValueError('Comparison reviewed source hash differs')
    observed = TRAFFIC['measure'](raw, frames, review_path) if traffic else CROSSING['events'](raw, frames)
    public_path, saved_path = (HERE / (prefix + suffix) for suffix in
                               ('-compatibility.json', '-processing.json'))
    public, saved = read(public_path), read(saved_path)
    key = 'traffic_response' if traffic else 'adjoining_crossing'
    measured = public['measurement_examples'][key]
    candidate = 'fallback1' if prefix.endswith('fallback1') else 'fallback2' if prefix.endswith('fallback2') else 'primary'
    if (not public['passed'] or not saved['passed'] or
            public['candidate_id'] != candidate or saved['candidate_id'] != candidate or
            not saved['recorded_only'] or not saved['originals_preserved'] or
            saved['timestamp_joins'].get('frames') != 600 or
            public['case_id'] != review['case_id'] or
            measured['sources']['native-raw-actors.jsonl'] != sha(raw) or
            measured['sources']['video_frames.jsonl'] != sha(frames) or
            measured['sources']['review.json'] != sha(review_path) or
            any(measured['value'][key] != observed[key] for key in
                ('first_stripe_body_frame','first_adjoining_road_frame','first_left_indicator_frame'))):
        raise ValueError('Comparison exact candidate source/receipt differs')
    if traffic and measured['value']['following_speed_drop_mps'] != observed['following_speed_drop_mps']:
        raise ValueError('Following response differs from saved source')
    return observed, {'case_id': public['case_id'], 'candidate_id': candidate,
                      'raw_sha256': sha(raw), 'frame_map_sha256': sha(frames),
                      'review_sha256':sha(review_path),
                      'compatibility_sha256': sha(public_path),
                      'saved_processing_sha256': sha(saved_path)}


def audit(comparison, candidate, tamper=False):
    if comparison not in ('signal_request_pair','following_response_pair'):
        raise ValueError('Unknown exact comparison')
    if comparison == 'signal_request_pair':
        if candidate not in ('primary','fallback1','fallback2'):
            raise ValueError('Unknown crossing candidate')
        names=('selected-probe1','selected-probe2')
    else:
        if candidate not in ('primary','fallback2'):
            raise ValueError('Unknown traffic candidate')
        names=('selected-traffic-clear_traffic','selected-traffic-following_brake')
    suffix='' if candidate=='primary' else '-'+candidate
    traffic=comparison=='following_response_pair'
    first, first_receipt=source(names[0]+suffix,traffic)
    second, second_receipt=source(names[1]+suffix,traffic)
    if tamper:
        second=dict(second,first_adjoining_road_frame=second['first_adjoining_road_frame']+1)
    fixed=('first_stripe_body_frame','first_adjoining_road_frame')
    if traffic:fixed+=('first_left_indicator_frame','oncoming_pre_crossing_mean_speed_mps','oncoming_post_crossing_min_speed_mps')
    for key in fixed:
        if first[key] != second[key]:
            raise ValueError('Comparison fixed source changed: '+key)
    if traffic:
        if second['following_speed_drop_mps'] <= first['following_speed_drop_mps']:
            raise ValueError('Following response difference absent')
        difference={'clear_drop_mps':first['following_speed_drop_mps'],
                    'response_drop_mps':second['following_speed_drop_mps']}
    else:
        if first['first_left_indicator_frame'] is None or second['first_left_indicator_frame'] is not None:
            raise ValueError('Prior signal difference absent')
        difference={'first_signal_frame':first['first_left_indicator_frame'],
                    'second_signal_frame':second['first_left_indicator_frame']}
    return {'format':'c109137-source-comparison-audit-v1','passed':True,
            'comparison':comparison,'candidate_id':candidate,'fixed_conditions':list(fixed),
            'deliberate_difference':difference,'cases':[first_receipt,second_receipt],
            'diagnostic_only':True,'original_native_observed':False,'legal_verdict':None}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--tamper',action='store_true')
    args=parser.parse_args()
    print(json.dumps(audit(args.comparison,args.candidate,args.tamper),sort_keys=True))
