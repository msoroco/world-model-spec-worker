"""Independent, source-bound review of selected emergency-lane contrasts."""
import argparse
import hashlib
import json
from pathlib import Path

AID = 'training__C405647__NRS-484B-267-2b__motor_vehicle_driver'
PAIRS = {'move_vs_adjacent': (1, 2), 'adverse_condition': (2, 3),
         'preparing_signal': (2, 4), 'officer_direction': (2, 5)}
SOURCES = ('vehicle_authorization', 'flashing_equipment',
           'flashing_qualification', 'lamp_pixels', 'lane_topology',
           'roadway_conditions', 'traffic_conditions', 'weather_conditions',
           'officer_direction', 'hand_signal_pixels')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison, left, right, output):
    key = comparison.removeprefix(AID + '__')
    require(comparison == AID + '__' + key and key in PAIRS,
            'Unknown exact comparison')
    left, right, output = Path(left), Path(right), Path(output)
    expected = [AID + f'__probe_0{n}' for n in PAIRS[key]]
    configs = [read(root / 'config.json') for root in (left, right)]
    require([c['case_id'] for c in configs] == expected,
            'Comparison must join selected cases in fixed order')
    for name in SOURCES:
        rel = 'source_context/' + name + '.txt'
        require(sha(left / rel) == sha(right / rel),
                'Fixed source context differs: ' + rel)
    for rel in ('road.xodr',):
        require(sha(left / rel) == sha(right / rel),
                'Fixed source road differs')
    for name in ('law_id', 'cell_id', 'actor', 'frozen_cell', 'rate_hz',
                 'duration_s', 'frames', 'cameras'):
        require(configs[0].get(name) == configs[1].get(name),
                'Fixed construction or camera policy changed: ' + name)
    traces = [rows(root / 'emergency-native.jsonl') for root in (left, right)]
    maps = [rows(root / 'video_frames.jsonl') for root in (left, right)]
    lamps = [read(root / 'lamp-pixel-review.json')['frames'] for root in (left, right)]
    signals = [read(root / 'signal-pixel-review.json')['frames'] for root in (left, right)]
    require(all(len(part) == 600 for part in traces + maps + lamps + signals),
            'Comparison lacks 600 source-joined frames')
    for root in (left, right):
        review = read(root / 'emergency-review.json')
        for name in SOURCES:
            ref = review['sources'][name]
            require(sha(root / ref['path']) == ref['sha256'],
                    'Review source hash mismatch: ' + name)
    for i in range(600):
        a, b = traces[0][i], traces[1][i]
        require(a['frame'] == b['frame'] == i and
                a['native_frame'] == maps[0][i]['native_frame'] and
                b['native_frame'] == maps[1][i]['native_frame'] and
                a['t_s'] == b['t_s'] == maps[0][i]['time_s'] == maps[1][i]['time_s'] and
                a['ego']['x_m'] == b['ego']['x_m'] and
                a['emergency_light_state'] == b['emergency_light_state'] and
                lamps[0][i] == lamps[1][i],
                'Frame, ego approach, or qualifying lamp contrast changed')
        if key == 'move_vs_adjacent':
            require(a['requested_ego_nonadjacent'] and not b['requested_ego_nonadjacent'] and
                    a['emergency'] == b['emergency'] and
                    a['weather_precipitation'] == b['weather_precipitation'] and
                    a['traffic'] == b['traffic'] and
                    (a['ego']['lane_id'] == -3 if i >= 160 else a['ego']['lane_id'] == -2) and
                    b['ego']['lane_id'] == -2,
                    'Move versus adjacent isolation failed')
        elif key == 'adverse_condition':
            require(a['ego'] == b['ego'] and a['emergency'] == b['emergency'] and
                    a['traffic'] is None and b['traffic']['lane_id'] == -3 and
                    a['weather_precipitation'] == 0 and b['weather_precipitation'] == 75 and
                    a['weather_wetness'] == 0 and b['weather_wetness'] == 80,
                    'Traffic and rain contrast failed')
        elif key == 'preparing_signal':
            require(a['ego'] == b['ego'] and a['emergency']['speed_mps'] > 0 and
                    b['emergency']['speed_mps'] == 0 and
                    not signals[0][i]['hand_signal_visible'] and
                    signals[1][i]['hand_signal_visible'] == (30 <= i < 500) and
                    not a['source_driver_hand_signal_requested'] and
                    b['source_driver_hand_signal_requested'],
                    'Moving versus preparing signal contrast failed')
        else:
            require(a['ego'] == b['ego'] and a['emergency'] == b['emergency'] and
                    not signals[0][i]['officer_direction_visible'] and
                    signals[1][i]['officer_direction_visible'] == (30 <= i < 500) and
                    not a['officer_hand_direction_requested'] and
                    b['officer_hand_direction_requested'],
                    'Separate officer direction contrast failed')
    report = {'format': 'c405647-comparison-audit-v1',
              'comparison_id': comparison, 'case_ids': expected,
              'source_sha256': [{name: sha(root / name) for name in
                                 ('config.json', 'road.xodr', 'emergency-review.json',
                                  'emergency-native.jsonl', 'video_frames.jsonl',
                                  'lamp-pixel-review.json', 'signal-pixel-review.json')}
                                for root in (left, right)],
              'checks': {'fixed_sources_road_camera_duration': True,
                         'full_original_frame_join': True,
                         'single_deliberate_branch_contrast': True},
              'diagnostic_fixture': all(read(root / 'emergency-review.json').get('review_kind') ==
                                        'synthetic_diagnostic' for root in (left, right)),
              'physical_or_legal_acceptance': False, 'passed': True}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison_id': comparison, 'passed': True,
                      'diagnostic_fixture': report['diagnostic_fixture']}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('comparison', 'left', 'right', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    audit(args.comparison, args.left, args.right, args.output)
