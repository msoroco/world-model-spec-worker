"""Audit the right-side near/earlier/later source timing comparison."""

import json
import shutil
import tempfile
from pathlib import Path

from prove_right_timing_comparison import BASE, EARLIER, check as check_earlier, rows, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LATER = REPO / '.runtime-work/c125714-later-compat-v2'
FIXED = ('road_geometry.json', 'road.xodr', 'video_frames.jsonl', 'trace.jsonl',
         'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
         'driver_reference.mkv')


def check_later(base, later):
    base, later = Path(base), Path(later)
    configs = [json.loads((root / 'config.json').read_text()) for root in (base, later)]
    if [c['selected_case_id'].rsplit('__', 1)[-1] for c in configs] != [
            'source_verified_other_right_near_time', 'source_verified_other_right_later']:
        raise ValueError('Wrong exact later timing comparison cases')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                'required_atoms', 'source_packets', 'recording_description',
                'ego_target_speed_mps', 'other_target_speed_mps'):
        if configs[0][key] != configs[1][key]:
            raise ValueError('Fixed timing config changed: ' + key)
    if configs[0]['other_release_frame'] != 20 or configs[1]['other_release_frame'] != 40:
        raise ValueError('Wrong near/later other release commands')
    if configs[1]['ego_release_frame'] != 20:
        raise ValueError('Wrong later ego release command')
    for name in FIXED:
        if sha(base / name) != sha(later / name):
            raise ValueError('Fixed timing source changed: ' + name)
    histories = [rows(root / 'crossing_history.jsonl') for root in (base, later)]
    if len(histories[0]) != 60 or len(histories[1]) != 60:
        raise ValueError('Timing comparison lacks 60 original frames')
    for near, delayed in zip(*histories):
        if near['frame'] != delayed['frame'] or near['time_s'] != delayed['time_s'] or near['ego'] != delayed['ego']:
            raise ValueError('Fixed ego body history changed')
    if any(row['other']['position_xy_m'] != [0, -8] for row in histories[1][:40]):
        raise ValueError('Other body moved before later release')
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in (base, later)]
    measurements = [report['measurements'] for report in reports]
    timings = [m['body_entry_timing']['value'] for m in measurements]
    sides = [m['approach_side']['value']['other_is_to_ego_right'] for m in measurements]
    if sides != [True, True] or timings[0]['first_body_entry']['ego'] != timings[1]['first_body_entry']['ego']:
        raise ValueError('Fixed right-side ego approach changed')
    deltas = [t['ego_minus_other_entry_time_s'] for t in timings]
    if abs(deltas[0] - .5) > 1e-9 or abs(deltas[1] + .5) > 1e-9:
        raise ValueError('Later original body-entry timing absent')
    return {'case_ids': [c['selected_case_id'] for c in configs],
            'fixed_source_sha256': {name: sha(base / name) for name in FIXED},
            'source_history_sha256': [sha(root / 'crossing_history.jsonl') for root in (base, later)],
            'ego_minus_other_entry_delta_s': [0.5, -0.5],
            'approximately_same_time_judgment': 'unresolved',
            'physical_acceptance_claimed': False}


def main():
    earlier = check_earlier(BASE, EARLIER)
    later = check_later(BASE, LATER)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c125714-later-negative-') as temp:
        target = Path(temp)
        for name in (*FIXED, 'config.json', 'crossing_history.jsonl', 'analysis-report.json'):
            shutil.copyfile(LATER / name, target / name)
        geometry = json.loads((target / 'road_geometry.json').read_text())
        geometry['intersection_id'] = 999
        (target / 'road_geometry.json').write_text(json.dumps(geometry) + '\n')
        try:
            check_later(BASE, target)
        except ValueError as error:
            if 'Fixed timing source changed: road_geometry.json' not in str(error):
                raise
            negative = str(error)
        else:
            raise AssertionError('Changed crossing identity passed later comparison')
    receipt = {'format': 'worker-c125714-right-three-way-timing-comparison',
               'near_earlier': earlier, 'near_later': later,
               'negative_rejected': negative, 'software_comparison_passed': True}
    path = ROOT / 'cases/source_verified_other_right_later/comparison-receipt.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparison': 'right_hand_entry_timing',
                      'ego_minus_other_entry_delta_s': [1.5, 0.5, -0.5],
                      'negative_rejected': negative,
                      'legal_judgment': 'unresolved'}))


if __name__ == '__main__':
    main()
