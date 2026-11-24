"""Source-bound software audit of the two planned controlled contrasts."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != 600 or [r['frame'] for r in rows] != list(range(600)):
        raise ValueError('Comparison source must have exactly 600 ordered frames')
    return rows


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for kind in ('obey', 'turn', 'dismount'):
        parser.add_argument('--' + kind, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = {kind: getattr(args, kind) / 'rider_native_samples.jsonl'
               for kind in ('obey', 'turn', 'dismount')}
    data = {kind: load(path) for kind, path in sources.items()}
    for rows in data.values():
        for r in rows:
            if (r['sign_id'], r['machine_class'], r['road_id'], r['approach_lane_id']) != (
                    'c104538-no-u-turn-1', 'bicycle', 1, -1):
                raise ValueError('Comparison changed sign/machine/approach identity')
    obey, turn, dismount = (data[kind] for kind in ('obey', 'turn', 'dismount'))
    if any(not r['mounted'] or r['u_turn_active'] for r in obey):
        raise ValueError('Obey source changed mounted through path')
    if any(not r['mounted'] for r in turn) or not any(r['u_turn_active'] for r in turn):
        raise ValueError('Mounted turn source changed')
    dismount_frame = next(i for i, r in enumerate(dismount) if not r['mounted'])
    first_turn_frame = next(i for i, r in enumerate(dismount) if r['u_turn_active'])
    if (dismount_frame >= first_turn_frame or
            any(r['mounted'] or not r['walking_machine'] for r in dismount[dismount_frame:]) or
            any(r['mounted'] for r in dismount if r['u_turn_active'])):
        raise ValueError('Exception source lacks persistent walking-machine ordering')
    pace = [((b['x_m']-a['x_m'])**2+(b['y_m']-a['y_m'])**2)**.5*20
            for a,b in zip(dismount[dismount_frame:],dismount[dismount_frame+1:])]
    if max(pace) > 2.05:
        raise ValueError('Requested walking controller pace differs')
    result = {
        'format': 'c104538-controlled-comparison-source-audit-v1',
        'scope': 'synthetic source software comparison only; no original Native or legal finding',
        'passed': True,
        'sources': {kind: {'path': str(path), 'sha256': sha(path)} for kind, path in sources.items()},
        'fixed_source_fields': ['sign_id', 'machine_class', 'road_id', 'approach_lane_id'],
        'mounted_comparison': {'obey_turn_frames': 0,
                               'turn_turn_frames': sum(r['u_turn_active'] for r in turn),
                               'different_requested_behavior': True},
        'exception_comparison': {'dismount_frame': dismount_frame,
                                 'first_turn_frame': first_turn_frame,
                                 'walking_turn_frames': sum(r['u_turn_active'] and r['walking_machine'] for r in dismount),
                                 'mounted_turn_frames': sum(r['u_turn_active'] and r['mounted'] for r in turn),
                                 'max_planned_walking_controller_pace_mps': max(pace),
                                 'pace_is_legal_cutoff': False,
                                 'pedestrian_rule_compliance_verified': False},
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'output_sha256': sha(args.output)}))


if __name__ == '__main__':
    main()
