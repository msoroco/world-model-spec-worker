"""Independently verify the source-bound controlled approach pair."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('controlled_1', 'controlled_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(negative=False):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparisons = plan['comparisons']
    if len(comparisons) != 1 or comparisons[0]['case_ids'] != [HERE.name + '__' + s for s in CASES]:
        raise ValueError('Exact controlled comparison changed')
    data = []
    sources = []
    for suffix in CASES:
        folder = HERE / 'current-fixture' / suffix
        path = folder / 'vehicle_poses.jsonl'
        context_path = folder / 'emergency_context.json'
        frames_path = folder / 'video_frames.jsonl'
        pose = rows(path)
        frames = rows(frames_path)
        context = json.loads(context_path.read_text())
        if len(pose) != 600 or len(frames) != 600:
            raise ValueError('Full 600-frame source comparison required')
        data.append((pose, frames, context))
        sources.append({'case_id': HERE.name + '__' + suffix,
                        'vehicle_poses_sha256': sha(path),
                        'video_frames_sha256': sha(frames_path),
                        'context_sha256': sha(context_path),
                        'road_sha256': sha(folder / 'road.xodr')})
    (a, af, ac), (b, bf, bc) = data
    if negative:
        b[150]['emergency']['x_m'] += 2
    if sources[0]['road_sha256'] != sources[1]['road_sha256']:
        raise ValueError('Fixed road geometry differs')
    if ac['emergency_vehicle_authorized'] != bc['emergency_vehicle_authorized'] or ac['qualifying_flash_equipment_reviewed'] != bc['qualifying_flash_equipment_reviewed'] or ac['officer_directed_otherwise'] != bc['officer_directed_otherwise']:
        raise ValueError('Fixed emergency qualification or officer context differs')
    for index, (one, two, frame_a, frame_b) in enumerate(zip(a, b, af, bf)):
        if frame_a != frame_b:
            raise ValueError('Fixed frame and time join differs at ' + str(index))
        if one['emergency'] != two['emergency']:
            raise ValueError('Fixed emergency trajectory or light state differs at ' + str(index))
        if index < 100 and one['ego'] != two['ego']:
            raise ValueError('Initial ego trajectory differs at ' + str(index))
        if one['ego']['heading_rad'] != two['ego']['heading_rad']:
            raise ValueError('Fixed ego heading differs at ' + str(index))
    speeds_a = [r['ego']['speed_mps'] for r in a[160:220]]
    speeds_b = [r['ego']['speed_mps'] for r in b[160:220]]
    if set(speeds_a) != {0} or set(speeds_b) != {3}:
        raise ValueError('Requested stop-versus-travel distinction absent')
    if any(abs(r['ego']['y_m']+2.5)>.15 for r in a[120:220]) or any(
            abs(r['ego']['y_m']+1.75)>.15 for r in b[120:220]):
        raise ValueError('Right-edge versus continued-lane distinction absent')
    return {'format': 'c405647-2f-current-comparison-audit',
            'comparison_id': comparisons[0]['comparison_id'],
            'case_ids': comparisons[0]['case_ids'],
            'fixed_road_actor_emergency_motion_lamps_time_join': True,
            'deliberate_difference': 'right-edge stop until passed versus continued travel',
            'measured_after_speed_mps': [0, 3],
            'sources': sources, 'diagnostic_only': True,
            'original_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    report = audit(args.negative)
    if not args.negative:
        path = HERE / 'current-public/comparison-audit.json'
        path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': report['comparison_id']}))
