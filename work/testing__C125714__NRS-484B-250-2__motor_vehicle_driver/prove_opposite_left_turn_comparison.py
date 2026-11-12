"""Check the observed turn against the fixed opposing left-intention approach."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / '.runtime-work/c125714-opposite-intends-compat-v1'
TURN = REPO / '.runtime-work/c125714-opposite-makes-compat-v1'
OUT = ROOT / 'cases/source_verified_opposite_makes_left'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(base=BASE, turn=TURN):
    fixed = ['road_geometry.json', 'road.xodr', 'turn_intent.json',
             'controller_history.jsonl', 'video_frames.jsonl',
             'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']
    for name in fixed:
        if not (base / name).is_file() or not (turn / name).is_file() or sha(base / name) != sha(turn / name):
            raise ValueError('Fixed source differs or is missing: ' + name)
    base_history, turn_history = rows(base / 'crossing_history.jsonl'), rows(turn / 'crossing_history.jsonl')
    base_evidence, turn_evidence = rows(base / 'capture/evidence.jsonl'), rows(turn / 'capture/evidence.jsonl')
    if not (len(base_history) == len(turn_history) == len(base_evidence) == len(turn_evidence) == 60):
        raise ValueError('Original histories have mismatched frame counts')
    if base_history[:31] != turn_history[:31] or base_evidence[:31] != turn_evidence[:31]:
        raise ValueError('Opposing approach changed before the declared turn')
    changed = []
    for index in range(31, 60):
        a = base_history[index]
        b = turn_history[index]
        if a['ego'] != b['ego'] or a['other'] == b['other']:
            raise ValueError('Turn difference does not isolate other actor motion')
        pa = next(p for p in base_evidence[index]['original_observations']['participants'] if p['actor_id'] == 102)
        pb = next(p for p in turn_evidence[index]['original_observations']['participants'] if p['actor_id'] == 102)
        if pa['heading_deg'] != 180 or pb['heading_deg'] != 270 or pb['position_m'][0] != 0:
            raise ValueError('Original heading/position does not show left turn')
        changed.append(index)
    for attempt, completion in ((base, False), (turn, True)):
        receipt = json.loads((attempt / 'compatibility.json').read_text())
        measurement = json.loads((attempt / 'analysis-report.json').read_text())['measurements']['opposite_approach']['value']
        if (receipt.get('passed') is not True or measurement.get('intended_maneuver') != 'left'
                or measurement.get('observed_turn_completed', False) != completion
                or measurement.get('left_turn_exception_judgment') != 'unresolved'):
            raise ValueError('Measured intention/turn outcome mismatch')
    return {'format': 'worker-opposite-left-turn-comparison',
            'fixed_sources': {name: sha(base / name) for name in fixed},
            'fixed_approach_frames': 31, 'changed_turn_frames': changed,
            'declared_difference': 'original other-actor post-approach left-turn motion',
            'legal_applicability': 'unresolved', 'physical_acceptance_claimed': False}


def main():
    receipt = audit()
    (OUT / 'comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fixed_approach_frames': receipt['fixed_approach_frames'],
                      'changed_turn_frames': len(receipt['changed_turn_frames'])}))


if __name__ == '__main__':
    main()
