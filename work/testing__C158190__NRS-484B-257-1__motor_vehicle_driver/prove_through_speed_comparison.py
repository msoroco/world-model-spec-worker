"""Independent CPU audit of the planned 3/7/11 m/s through-traffic comparison.

Read original synthetic Native-shaped source rows and recorded-only receipts.
This does not decide whether a real driver faced an immediate hazard.
"""

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SPEEDS = (3, 7, 11)
PREFIX = ROOT.name + '__yield_nearest_view_through_speed_'
FIXED_FILES = (
    'road.xodr', 'road_context.json', 'control_context.json',
    'capture/native_map_facts.json', 'video_frames.jsonl',
    'approach_history.jsonl', 'visibility_rays.jsonl',
    'capture/native/frames.jsonl',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def center(vertices):
    if len(vertices) != 8 or any(len(vertex) != 3 for vertex in vertices):
        raise ValueError('Original actor body vertices are incomplete')
    return tuple(sum(vertex[axis] for vertex in vertices) / 8 for axis in range(3))


def normalized_support(text, speed):
    return text.replace('yield_nearest_view_through_speed_' + str(speed),
                        'yield_nearest_view_through_speed_TARGET')


def audit(roots, configs, histories, *, verify_files=True):
    if len(roots) != 3 or len(configs) != 3 or len(histories) != 3:
        raise ValueError('Comparison requires three exact cases')
    common = copy.deepcopy(configs[0])
    common['selected_case_id'] = PREFIX + 'TARGET'
    common['supported_case_ids'][0] = PREFIX + 'TARGET'
    for speed, config in zip(SPEEDS, configs):
        if config['selected_case_id'] != PREFIX + str(speed):
            raise ValueError('Comparison selected another exact case')
        if (config['law_id'], config['cell_id'], config['rate_hz'],
                config['duration_s']) != ('NRS-484B-257-1', 'C158190', 20, 30):
            raise ValueError('Fixed law, cell or capture profile changed')
        check = copy.deepcopy(config)
        check['selected_case_id'] = PREFIX + 'TARGET'
        check['supported_case_ids'][0] = PREFIX + 'TARGET'
        if check != common:
            raise ValueError('Fixed config, cameras or spawn changed')
    if verify_files:
        for name in FIXED_FILES:
            if len({sha(root / name) for root in roots}) != 1:
                raise ValueError('Fixed original source changed: ' + name)
        for name in ('runner.py', 'yield_controller.py'):
            if len({normalized_support((root / name).read_text(), speed)
                    for root, speed in zip(roots, SPEEDS)}) != 1:
                raise ValueError('Fixed runner or ego controller changed: ' + name)
        source = (roots[0] / 'yield_motion.py').read_text()
        for root, speed in zip(roots, SPEEDS):
            motion = (root / 'yield_motion.py').read_text()
            if f'THROUGH_TARGET_MPS = {speed}.0' not in motion:
                raise ValueError('Through motion target differs from declared speed')
            if motion.replace(f'THROUGH_TARGET_MPS = {speed}.0',
                              'THROUGH_TARGET_MPS = TARGET') != source.replace(
                                  'THROUGH_TARGET_MPS = 3.0',
                                  'THROUGH_TARGET_MPS = TARGET'):
                raise ValueError('Another motion-control condition changed')
    ego_histories = []
    speed_samples = []
    for target, history in zip(SPEEDS, histories):
        if len(history) != 600:
            raise ValueError('Original body history lacks 600 frames')
        if any(row['frame'] != 100 + index or row['ego']['actor_id'] != 101
               or row['through']['actor_id'] != 23
               for index, row in enumerate(history)):
            raise ValueError('Original frame or actor identity changed')
        ego_histories.append([row['ego'] for row in history])
        through = [center(row['through']['body_vertices_m']) for row in history[:51]]
        if any(abs(actual - expected) > 1e-6 for actual, expected in
               zip(through[0], (1.8, 20.0, 0.75))):
            raise ValueError('Through actor spawn changed')
        intervals = [(through[index][1] - through[index + 1][1]) / .05
                     for index in range(50)]
        if any(abs(value - target) > 1e-6 for value in intervals):
            raise ValueError('Original through body speed differs from target')
        speed_samples.append(round(sum(intervals) / len(intervals), 6))
    if not (ego_histories[0] == ego_histories[1] == ego_histories[2]):
        raise ValueError('Fixed ego body trajectory changed')
    return speed_samples


def main():
    roots = [REPO / f'.runtime-work/c158190-through-speed-{speed}-compat-v2'
             for speed in SPEEDS]
    configs = [read(root / 'config.json') for root in roots]
    histories = [rows(root / 'interaction_history.jsonl') for root in roots]
    measured = audit(roots, configs, histories)
    negative = []
    tampered = copy.deepcopy(configs)
    tampered[1]['cameras'][0]['width'] += 1
    try:
        audit(roots, tampered, histories, verify_files=False)
    except ValueError:
        negative.append('changed_camera_rejected')
    tampered = copy.deepcopy(histories)
    tampered[1][10]['ego']['body_vertices_m'][0][0] += 1
    try:
        audit(roots, configs, tampered, verify_files=False)
    except ValueError:
        negative.append('changed_ego_history_rejected')
    tampered = copy.deepcopy(histories)
    tampered[2][10]['through']['body_vertices_m'][0][1] += 1
    try:
        audit(roots, configs, tampered, verify_files=False)
    except ValueError:
        negative.append('changed_through_speed_rejected')
    if len(negative) != 3:
        raise ValueError('Comparison negative checks failed')
    receipts = []
    for speed, root in zip(SPEEDS, roots):
        saved = REPO / f'.runtime-work/c158190-through-speed-{speed}-saved-v1/v0001/processing.json'
        result = read(saved)
        if (result.get('passed') is not True or result.get('recorded_only') is not True
                or result.get('originals_preserved') is not True
                or result.get('physical_acceptance_claimed') is not False
                or result.get('legal_acceptance_claimed') is not False):
            raise ValueError('Saved processing receipt is incomplete')
        receipts.append({'case_id': PREFIX + str(speed),
                         'original_body_sha256': sha(root / 'interaction_history.jsonl'),
                         'saved_processing_sha256': sha(saved)})
    print(json.dumps({'format': 'c158190-through-speed-independent-comparison-audit',
                      'comparison_id': 'same_approach_through_speed_3_7_11',
                      'fixed_source_sha256': {name: sha(roots[0] / name)
                                              for name in FIXED_FILES},
                      'measured_through_speed_mps': measured,
                      'negative_checks': negative, 'receipts': receipts,
                      'software_comparison_passed': True,
                      'native_feasibility_proven': False,
                      'legal_conclusion': 'unresolved'}, indent=2))


if __name__ == '__main__':
    main()
