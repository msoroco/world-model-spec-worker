"""Independent ending versus continuing highway diagnostic source comparison."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ending_road_measurement import measure as measure_ending
from highway_continuity_source import measure_originals as measure_continuing


def _read(path):
    path = Path(path)
    return json.loads(path.read_text())['files'], sha256(path.read_bytes()).hexdigest()


def _measure(files, topology_name, method):
    with TemporaryDirectory() as temp:
        root = Path(temp)
        (root / topology_name).write_text(files[topology_name])
        (root / 'intersection_participants.jsonl').write_text(
            files['intersection_participants.jsonl'])
        return method(root / topology_name, root / 'intersection_participants.jsonl')


def _frame_offsets(files):
    rows = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()
            if line.strip()]
    if not rows or any(row.get('video_frame') != index for index, row in enumerate(rows)):
        raise ValueError('Highway comparison frame map is incomplete')
    times = [row['time_s'] for row in rows]
    if any(abs(b - a - .05) > 1e-4 for a, b in zip(times, times[1:])):
        raise ValueError('Highway comparison frame map is not 20 Hz')
    return [round(value - times[0], 5) for value in times]


def audit_files(ending, continuing, ending_hash, continuing_hash):
    start = json.loads(ending['intersection_topology.json'])
    other = json.loads(continuing['highway_pair_topology.json'])
    a = _measure(ending, 'intersection_topology.json', measure_ending)
    b = _measure(continuing, 'highway_pair_topology.json', measure_continuing)
    if a['approaches']['subject']['continues_beyond_junction']:
        raise ValueError('Ending comparison point continues in original source')
    if b['selected_category'] != 'continuing':
        raise ValueError('Continuing comparison point absent from original source')
    fixed = {
        'junction_id': (str(start['junction_id']), str(other['junction_id'])),
        'conflict_polygon_xy': (start['conflict_polygon_xy'], other['conflict_polygon_xy']),
        'through_road_id': (json.loads(ending['control_inventory.json'])['through_approach_road_id'],
                            other['routes']['other'][0]['road_id']),
        'through_lane_id': (json.loads(ending['control_inventory.json'])['through_approach_lane_id'],
                            other['routes']['other'][0]['lane_id']),
        'control_state': (json.loads(ending['control_inventory.json']),
                          json.loads(continuing['control_inventory.json'])),
        'video_frame_schedule': (_frame_offsets(ending), _frame_offsets(continuing)),
    }
    for key, (left, right) in fixed.items():
        if key == 'control_state':
            for inventory in (left, right):
                if (inventory.get('format') != 'worker-ending-road-original-control-inventory'
                        or any(inventory.get(name) for name in
                               ('ending_landmarks', 'through_landmarks', 'junction_lights'))):
                    raise ValueError('Changed fixed no-control inventory')
            continue
        if left != right:
            raise ValueError('Changed fixed highway comparison source: ' + key)
    if (a['approaches']['subject']['highway_id'] ==
            other['routes']['continuing'][0]['road_id']):
        raise ValueError('Comparison subject road identity did not change')
    return {'format': 'worker-highway-continuity-comparison-proof',
            'ending_diagnostic_sha256': ending_hash,
            'continuing_diagnostic_sha256': continuing_hash,
            'fixed_source_checks': list(fixed),
            'ending_subject_continues': False, 'continuing_subject_continues': True,
            'ending_entry_delta_s': a['entry_delta_s'],
            'continuing_entry_delta_s': b['entry_delta_s'],
            'actual_native_capture_claimed': False, 'legal_judgment_claimed': False}


def audit(ending_path, continuing_path):
    ending, ending_hash = _read(ending_path)
    continuing, continuing_hash = _read(continuing_path)
    return audit_files(ending, continuing, ending_hash, continuing_hash)


def require_retained_pair_bindings(ending_binding, continuing_binding):
    """Validate both original binding hashes and require one selected Native pair."""
    bindings = (ending_binding, continuing_binding)
    for binding in bindings:
        if not isinstance(binding, dict) or binding.get('format') != 'worker-controlled-highway-route-pair':
            raise ValueError('Missing controlled Native route-pair binding')
        digest = binding.get('route_pair_sha256')
        payload = {key: value for key, value in binding.items()
                   if key != 'route_pair_sha256'}
        actual = sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                   allow_nan=False).encode()).hexdigest()
        if actual != digest:
            raise ValueError('Stale controlled Native route-pair binding')
        if set(binding.get('routes', {})) != {'ending', 'continuing', 'other'}:
            raise ValueError('Incomplete controlled Native route-pair binding')
    if bindings[0]['route_pair_sha256'] != bindings[1]['route_pair_sha256']:
        raise ValueError('Changed controlled Native route-pair binding')
    return bindings[0]['route_pair_sha256']


def audit_attempts(ending_attempt, continuing_attempt):
    """Check retained original sources from two saved Native attempts."""
    names = ('intersection_participants.jsonl', 'video_frames.jsonl',
             'control_inventory.json', 'controlled_route_pair.json')
    roots = (Path(ending_attempt), Path(continuing_attempt))
    required = (names + ('intersection_topology.json',),
                names + ('highway_pair_topology.json',))
    files = []
    for root, needed in zip(roots, required):
        if any(not (root / name).is_file() for name in needed):
            raise ValueError('Missing original highway comparison source')
        files.append({name: (root / name).read_text() for name in needed})
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            if not (root / (camera + '.mkv')).is_file():
                raise ValueError('Missing named highway comparison camera: ' + camera)
    result = audit_files(files[0], files[1],
                         sha256(''.join(files[0].values()).encode()).hexdigest(),
                         sha256(''.join(files[1].values()).encode()).hexdigest())
    binding = json.loads(files[0]['controlled_route_pair.json'])
    result['controlled_route_pair_sha256'] = require_retained_pair_bindings(
        binding, json.loads(files[1]['controlled_route_pair.json']))
    ending_topology = json.loads(files[0]['intersection_topology.json'])
    continuing_topology = json.loads(files[1]['highway_pair_topology.json'])
    if (str(ending_topology['junction_id']) != binding['junction_id'] or
            str(continuing_topology['junction_id']) != binding['junction_id'] or
            continuing_topology['map_name'] != binding['map_name']):
        raise ValueError('Controlled route-pair map or junction differs from originals')
    for name, selected in binding['routes'].items():
        observed = continuing_topology['routes'][name]
        if observed[:len(selected)] != selected:
            raise ValueError('Controlled route-pair path differs from original topology: ' + name)
    subject_lane = ending_topology['lanes'][ending_topology['subject_approach_lane']]
    if subject_lane['highway_id'] != 'native-road:' + str(binding['routes']['ending'][0]['road_id']):
        raise ValueError('Ending original approach differs from controlled route pair')
    result['attempt_source_hashes'] = [
        {name: sha256((root / name).read_bytes()).hexdigest() for name in needed}
        for root, needed in zip(roots, required)]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ending')
    parser.add_argument('--continuing')
    parser.add_argument('--output', required=True)
    parser.add_argument('--ending-attempt')
    parser.add_argument('--continuing-attempt')
    args = parser.parse_args()
    if not ((args.ending_attempt and args.continuing_attempt) or
            (args.ending and args.continuing)):
        raise ValueError('Select both diagnostic sources or both saved attempts')
    result = (audit_attempts(args.ending_attempt, args.continuing_attempt)
              if args.ending_attempt and args.continuing_attempt else
              audit(args.ending, args.continuing))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'fixed_source_checks': result['fixed_source_checks']}))


if __name__ == '__main__':
    main()
