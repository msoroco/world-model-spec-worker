"""Independently compare the two unselected synthetic Native/Core attempts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
IDENTITY_KEYS = {'case_id', 'selected_case_id', 'supported_case_ids', 'case_suffix', 'case'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fixed_config(config):
    return {key: value for key, value in config.items() if key not in IDENTITY_KEYS}


def check_pair(left, right):
    a, b = [json.loads((path/'config.json').read_text()) for path in (left, right)]
    if fixed_config(a) != fixed_config(b):
        raise AssertionError('Controlled capture configuration differs')
    if a['case_suffix'] != 'witness_1' or b['case_suffix'] != 'witness_2':
        raise AssertionError('Controlled case identities differ')
    if (a['rate_hz'], a['duration_s']) != (20, 24):
        raise AssertionError('Controlled rate or duration differs')
    if sha(left/'road.xodr') != sha(right/'road.xodr'):
        raise AssertionError('Controlled authored road differs')
    for name in ('video_frames.jsonl', 'context.json'):
        if sha(left/name) != sha(right/name):
            raise AssertionError('Controlled source differs: '+name)
    for name in ('overview', 'approach', 'sign_reference', 'driver_reference'):
        if not (left/(name+'.mkv')).is_file() or not (right/(name+'.mkv')).is_file():
            raise AssertionError('Controlled camera source missing: '+name)
    sources = [rows(path/'native_samples.jsonl') for path in (left, right)]
    maps = [rows(path/'video_frames.jsonl') for path in (left, right)]
    if any(len(data) != 480 for data in sources+maps):
        raise AssertionError('Controlled frame inventory differs')
    for index, (x, y) in enumerate(zip(*sources)):
        if (x['native_frame'], x['time_s']) != (y['native_frame'], y['time_s']):
            raise AssertionError('Controlled Native frame/time differs')
        if maps[0][index] != maps[1][index]:
            raise AssertionError('Controlled video frame join differs')
    if sources[0][0] != sources[1][0]:
        raise AssertionError('Controlled initial body and lane differ')
    reviews = [json.loads((path/'sign-review.json').read_text()) for path in (left, right)]
    for index, review in enumerate(reviews):
        path = (left, right)[index]
        if (review['native_samples_sha256'] != sha(path/'native_samples.jsonl') or
            review['frame_map_sha256'] != sha(path/'video_frames.jsonl') or
            review['video_sha256'] != sha(path/'approach.mkv') or
            review['pixel_review_sha256'] != sha(path/'pixel_review.jsonl') or
            review['approach_frames'] != len(rows(path/'pixel_review.jsonl'))):
            raise AssertionError('Sign review lost source binding')
    variable_hash_keys = {'native_samples_sha256', 'video_sha256',
                          'pixel_review_sha256', 'approach_frames',
                          'full_body_and_sign_visible_frames'}
    if ({k: v for k, v in reviews[0].items() if k not in variable_hash_keys} !=
        {k: v for k, v in reviews[1].items() if k not in variable_hash_keys}):
        raise AssertionError('Controlled sign review context differs')
    values = []
    for path in (left, right):
        result = json.loads((path/'result.json').read_text())
        report = json.loads((path/'analysis-report.json').read_text())
        value = report['measurements']['signed_u_turn']['value']
        if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
            raise AssertionError('Synthetic attempt claims delivery or verdict')
        if value['source_hashes']['native_samples.jsonl'] != sha(path/'native_samples.jsonl'):
            raise AssertionError('Measured Native source differs')
        values.append(value)
    if values[0]['u_turn_within_governed_region_observed'] is not False:
        raise AssertionError('Straight control measured as U-turn')
    if (values[1]['u_turn_within_governed_region_observed'] is not True or
        values[1]['reversal_native_frame'] != 371 or
        values[1]['complete_body_inside_governed_region_at_reversal'] is not True or
        values[1]['opposing_lane_exit_observed'] is not True):
        raise AssertionError('U-turn probe lacks complete-body reversal and exit')
    return {'passed': True, 'frame_count': 480, 'fixed_road_sha256': sha(left/'road.xodr'),
            'fixed_config_sha256': hashlib.sha256(json.dumps(fixed_config(a), sort_keys=True).encode()).hexdigest(),
            'same_initial_native_body': True, 'same_frame_schedule': True,
            'same_sign_review_context': True, 'straight_u_turn': False,
            'probe_u_turn': True, 'probe_reversal_frame': 371,
            'scope': 'unselected synthetic software comparison only'}


def main():
    attempts = []
    for suffix in ('witness_1', 'witness_2'):
        receipt = json.loads((FOLDER/('synthetic-core-'+suffix+'.log')).read_text())
        attempts.append(Path(receipt['scratch'])/'attempt')
    result = check_pair(*attempts)
    config = json.loads((attempts[1]/'config.json').read_text())
    config['duration_s'] += 1
    if fixed_config(config) == fixed_config(json.loads((attempts[0]/'config.json').read_text())):
        raise AssertionError('Changed fixed duration escaped comparison')
    result['changed_fixed_duration_rejected'] = True
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
