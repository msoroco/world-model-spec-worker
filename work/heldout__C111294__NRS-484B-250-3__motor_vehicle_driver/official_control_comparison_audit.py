"""Independent controlled comparison of absent versus governing Native control."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def _read(files, name):
    if name not in files or not files[name]:
        raise ValueError('Missing original comparison source: ' + name)
    return json.loads(files[name])


def _rows(files, name):
    if name not in files or not files[name]:
        raise ValueError('Missing original comparison source: ' + name)
    rows = [json.loads(line) for line in files[name].splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty original comparison source: ' + name)
    return rows


def _topology_core(topology):
    lanes = {key:{k:v for k,v in lane.items() if k in ('highway_id','junction_id','successors')}
             for key,lane in topology['lanes'].items()}
    return dict(topology, lanes=lanes)


def audit_sources(uncontrolled, controlled):
    names = ('intersection_participants.jsonl', 'video_frames.jsonl', 'trace.jsonl')
    for name in names:
        if name not in uncontrolled or name not in controlled or uncontrolled[name] != controlled[name]:
            raise ValueError('Official-control comparison changed fixed original ' + name)
    plain_topology = _read(uncontrolled, 'intersection_topology.json')
    device_topology = _read(controlled, 'intersection_topology.json')
    if _topology_core(plain_topology) != _topology_core(device_topology):
        raise ValueError('Official-control comparison changed connected lane topology')
    inventory = _read(uncontrolled, 'control_inventory.json')
    if (inventory.get('format') != 'worker-ending-road-original-control-inventory' or
            str(inventory.get('junction_id')) != str(plain_topology['junction_id']) or
            any(inventory.get(k) for k in ('ending_landmarks','through_landmarks','junction_lights'))):
        raise ValueError('Uncontrolled case lacks original no-control inventory')
    context = _read(controlled, 'official_device_context.json')
    lane = device_topology['lanes'][device_topology['subject_approach_lane']]
    if (str(context.get('junction_id')) != str(device_topology['junction_id']) or
            context.get('affected_road_id') != lane.get('road_id') or
            context.get('affected_lane_id') != lane.get('lane_id') or
            not context.get('opendrive_signal_id')):
        raise ValueError('Official device does not govern fixed ending approach')
    frames = _rows(controlled, 'video_frames.jsonl')
    states = _rows(controlled, 'official_device_states.jsonl')
    if len(states) != len(frames):
        raise ValueError('Official device state/frame length differs')
    for state,frame in zip(states,frames):
        if ((state.get('frame'),state.get('time_s')) !=
                (frame.get('carla_frame'),frame.get('time_s')) or
                state.get('device_id') != context.get('device_id') or
                state.get('value') != state.get('native_state') or not state.get('native_state')):
            raise ValueError('Official device state/frame join differs')
    return {'format':'worker-official-control-comparison-audit',
            'comparison_id':'official_control_exception',
            'fixed_originals':{name:sha256(uncontrolled[name].encode()).hexdigest() for name in names},
            'fixed_topology_core':_topology_core(plain_topology),
            'uncontrolled_inventory_sha256':sha256(uncontrolled['control_inventory.json'].encode()).hexdigest(),
            'controlled_context_sha256':sha256(controlled['official_device_context.json'].encode()).hexdigest(),
            'controlled_state_sha256':sha256(controlled['official_device_states.jsonl'].encode()).hexdigest(),
            'device_frames':len(states),'physical_control_status_claimed':False,
            'legal_exception_claimed':False}


def audit_attempts(uncontrolled_attempt, controlled_attempt):
    """Audit retained original files from two saved Native attempts."""
    names = ('intersection_participants.jsonl', 'video_frames.jsonl',
             'trace.jsonl', 'intersection_topology.json',
             'control_inventory.json', 'official_device_context.json',
             'official_device_states.jsonl')
    roots = (Path(uncontrolled_attempt), Path(controlled_attempt))
    if roots[0].resolve() == roots[1].resolve():
        raise ValueError('Official-control comparison requires distinct attempts')
    files = []
    for root, needed in zip(roots, (names[:5], names[:4] + names[5:])):
        if not root.is_dir():
            raise ValueError('Missing original comparison attempt: ' + str(root))
        missing = [name for name in needed if not (root / name).is_file()]
        if missing:
            raise ValueError('Missing original comparison source: ' + missing[0])
        files.append({name: (root / name).read_text() for name in needed})
    result = audit_sources(*files)
    result['original_source_sha256'] = [
        {name: sha256((root / name).read_bytes()).hexdigest() for name in source}
        for root, source in zip(roots, files)
    ]
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--uncontrolled')
    parser.add_argument('--controlled')
    parser.add_argument('--uncontrolled-attempt')
    parser.add_argument('--controlled-attempt')
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.uncontrolled_attempt and args.controlled_attempt and not (args.uncontrolled or args.controlled):
        result = audit_attempts(args.uncontrolled_attempt, args.controlled_attempt)
    elif args.uncontrolled and args.controlled and not (args.uncontrolled_attempt or args.controlled_attempt):
        first=json.loads(Path(args.uncontrolled).read_text())['files']
        second=json.loads(Path(args.controlled).read_text())['files']
        result = audit_sources(first,second)
    else:
        parser.error('select both diagnostic recipes or both saved attempts')
    if args.output:
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
