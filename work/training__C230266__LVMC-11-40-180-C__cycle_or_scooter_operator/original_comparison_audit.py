"""Independent source-bound comparison of two original sidewalk attempts."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import check_result, check_source_rows, check_review

PAIRS = {'signal': ('probe_a', 'probe_b', 'signal_frame', 'pause_window_frames'),
         'yield': ('probe_a', 'probe_c', 'pause_window_frames', 'signal_frame')}
ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(attempt, review_path, receipt_path, case):
    attempt = Path(attempt).resolve()
    result_path = attempt / 'result.json'
    result = json.loads(result_path.read_text())
    check_result(result, case)
    receipt = json.loads(Path(receipt_path).read_text())
    if (receipt.get('format') != 'worker-delivery-audit' or
            receipt.get('passed') is not True or receipt.get('case_id') != case or
            receipt.get('source_result_sha256') != sha(result_path)):
        raise ValueError('Missing source-bound individual delivery audit')
    paths = {name: attempt / filename for name, filename in {
        'actors': 'sidewalk-actors.jsonl', 'cameras': 'camera-frames.jsonl',
        'video_frames': 'video_frames.jsonl',
        'microphone': 'pedestrian-microphone.json',
        'microphone_frames': 'pedestrian-microphone-frames.jsonl',
        'map': 'sidewalk-map-readback.json', 'road': 'road.xodr'}.items()}
    if any(not path.is_file() for path in paths.values()):
        raise ValueError('Missing original comparison source')
    microphone = json.loads(paths['microphone'].read_text())
    pcm = attempt / microphone['pcm_path']
    if not pcm.is_file() or sha(pcm) != microphone['pcm_sha256']:
        raise ValueError('Original microphone bytes changed')
    paths['pcm'] = pcm
    review = json.loads((attempt / review_path).read_text())
    check_review(review, case, paths)
    if receipt.get('human_review_sha256') != sha(attempt / review_path):
        raise ValueError('Individual audit binds another source review')
    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines()]
    actors = rows(paths['actors'])
    check_source_rows(actors, rows(paths['cameras']), rows(paths['video_frames']),
                      rows(paths['microphone_frames']))
    config = json.loads((attempt / 'config.json').read_text())
    if config.get('case_id') != case:
        raise ValueError('Comparison config belongs to another case')
    return {'config': config, 'result': result, 'review': review,
            'actors': actors, 'road_sha256': sha(paths['road']),
            'map': json.loads(paths['map'].read_text()),
            'source_result_sha256': sha(result_path),
            'delivery_receipt_sha256': sha(receipt_path)}


def compare(pair, a, b):
    suffix_a, suffix_b, changed, fixed = PAIRS[pair]
    if a['config'][changed] == b['config'][changed]:
        raise ValueError('Comparison lacks requested variable difference')
    if a['config'][fixed] != b['config'][fixed]:
        raise ValueError('Comparison changed fixed request')
    excluded = {'case_id', 'selected_case_id', 'target_request',
                'signal_frame', 'pause_window_frames'}
    if ({key: value for key, value in a['config'].items() if key not in excluded} !=
            {key: value for key, value in b['config'].items() if key not in excluded} or
            a['road_sha256'] != b['road_sha256'] or a['map'] != b['map']):
        raise ValueError('Comparison changed fixed sidewalk context')
    for key in ('device_class_reviewed', 'sidewalk_context_reviewed',
                'pedestrian_identity_reviewed', 'microphone_placement_reviewed'):
        if not a['review'].get(key) or not b['review'].get(key):
            raise ValueError('Comparison fixed context lacks independent review')
    am, bm = a['result']['measured_values'], b['result']['measured_values']
    if any(m.get('first_full_ahead_frame') is None for m in (am, bm)):
        raise ValueError('Comparison lacks original completed pass')
    if pair == 'signal':
        if (am.get('first_rider_pause_frame') is None or
                bm.get('first_rider_pause_frame') is None or
                am.get('first_microphone_pulse_video_frame_approx') is None or
                bm.get('first_microphone_pulse_video_frame_approx') is not None):
            raise ValueError('Original audible-signal contrast missing')
    elif (am.get('first_rider_pause_frame') is None or
          bm.get('first_rider_pause_frame') is not None or
          any(m.get('first_microphone_pulse_video_frame_approx') is None
              for m in (am, bm))):
        raise ValueError('Original yield-response contrast missing')
    return {'format': 'c230266-original-comparison-audit-v1',
            'comparison_id': AID + ('__comparison' if pair == 'signal'
                                     else '__yield_comparison'),
            'case_ids': [AID + '__' + suffix_a, AID + '__' + suffix_b],
            'passed': True, 'road_sha256': a['road_sha256'],
            'source_result_sha256': [a['source_result_sha256'], b['source_result_sha256']],
            'delivery_receipt_sha256': [a['delivery_receipt_sha256'],
                                        b['delivery_receipt_sha256']],
            'requested_difference': changed,
            'observed_measurements': {suffix_a: am, suffix_b: bm},
            'legal_verdict_claimed': False}


def selftest(pair, negative):
    suffix_a, suffix_b, changed, fixed = PAIRS[pair]
    base = {'case_id': AID + '__' + suffix_a, 'signal_frame': 100,
            'pause_window_frames': [200, 250], 'duration_s': 30,
            'rate_hz': 20, 'cameras': ['four fixed sources']}
    ca, cb = dict(base), dict(base, case_id=AID + '__' + suffix_b)
    ca[changed], cb[changed] = (100, None) if pair == 'signal' else ([200, 250], [0, 0])
    if pair == 'signal':
        cb['signal_frame'] = None
    else:
        cb['pause_window_frames'] = [0, 0]
    measured_a = {'first_full_ahead_frame': 400, 'first_rider_pause_frame': 200,
                  'first_microphone_pulse_video_frame_approx': 100}
    measured_b = dict(measured_a)
    if pair == 'signal':
        measured_b['first_microphone_pulse_video_frame_approx'] = None
    else:
        measured_b['first_rider_pause_frame'] = None
    review = {key: True for key in ('device_class_reviewed',
              'sidewalk_context_reviewed', 'pedestrian_identity_reviewed',
              'microphone_placement_reviewed')}
    def item(config, measured):
        return {'config': config, 'result': {'measured_values': measured},
                'review': review, 'road_sha256': 'same-road', 'map': {'lane_id': -2},
                'source_result_sha256': 'source', 'delivery_receipt_sha256': 'receipt'}
    a, b = item(ca, measured_a), item(cb, measured_b)
    if negative:
        b['road_sha256'] = 'different-road'
        compare(pair, a, b)
        raise AssertionError('Changed original road accepted')
    proof = compare(pair, a, b)
    print(json.dumps({'comparison_id': proof['comparison_id'], 'selftest': 'passed'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', choices=tuple(PAIRS), required=True)
    parser.add_argument('--selftest', choices=('positive', 'negative'))
    for option in ('attempt-a', 'attempt-b', 'review-a', 'review-b',
                   'receipt-a', 'receipt-b'):
        parser.add_argument('--' + option)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.pair, args.selftest == 'negative')
    else:
        if not all((args.attempt_a, args.attempt_b, args.review_a,
                    args.review_b, args.receipt_a, args.receipt_b, args.output)):
            parser.error('Original comparisons require both attempts, reviews and receipts')
        one, two = PAIRS[args.pair][:2]
        a = load(args.attempt_a, args.review_a, args.receipt_a, AID + '__' + one)
        b = load(args.attempt_b, args.review_b, args.receipt_b, AID + '__' + two)
        proof = compare(args.pair, a, b)
        Path(args.output).write_text(json.dumps(proof, indent=2) + '\n')
        print(json.dumps(proof))
