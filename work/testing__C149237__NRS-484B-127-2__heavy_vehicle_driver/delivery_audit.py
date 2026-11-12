"""Independent original-source checks for NRS 484B.127(2) delivery.

This module deliberately does not infer physical completion from a diagnostic.
The source checks can be exercised on diagnostic fixtures; delivery acceptance
requires a complete Native capture and the separate pixel/physical review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED_CHECKS = ('native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty original source: ' + path.name)
    return rows


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def source_join(root, case_id, *, expected_frames):
    """Validate all retained truck rows against the original frame and trace.

    `expected_frames` is supplied by the caller. Delivery supplies the planned
    rate times duration; small values are useful only for software fixtures.
    """
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('Original config differs from exact case')
    names = ('truck_history.jsonl', 'video_frames.jsonl', 'trace.jsonl')
    history, mapping, trace = (load_rows(root / name) for name in names)
    evidence = load_rows(root/'capture/evidence.jsonl')
    if not (len(history) == len(mapping) == len(trace) == len(evidence) == expected_frames):
        raise ValueError('Original source frame count differs from planned capture')
    context = json.loads((root / 'road_context.json').read_text())
    if (not context.get('native_map_id') or type(context.get('road_id')) is not int
            or type(context.get('lane_id')) is not int
            or type(context.get('same_direction_lane_count')) is not int
            or context['same_direction_lane_count'] < 1):
        raise ValueError('Missing original road context')
    ids = None
    previous_frame, previous_time = -1, -math.inf
    inventory_ids = None
    for index, (row, frame, packet, observed) in enumerate(zip(history, mapping, trace, evidence)):
        native = frame.get('carla_frame', frame.get('native_frame'))
        time_s = frame.get('time_s')
        if (type(native) is not int or native <= previous_frame or
                frame.get('video_frame') != index or row.get('frame') != native or
                packet.get('frame') != native or not finite_number(time_s) or
                time_s <= previous_time or not finite_number(row.get('time_s')) or
                abs(row['time_s'] - time_s) > 1e-3):
            raise ValueError('Original frame/time join differs')
        packet_time = packet.get('time_s')
        if packet_time is not None and (not finite_number(packet_time) or abs(packet_time-time_s) > 1e-3):
            raise ValueError('Original trace time join differs')
        observations = observed.get('original_observations', {})
        actors = observations.get('participants')
        if (observed.get('original_frame') != native or
                not finite_number(observed.get('recording_time_s')) or
                abs(observed['recording_time_s']-time_s) > 1e-3):
            raise ValueError('Original evidence frame/time join differs')
        if (not isinstance(actors, list) or not actors or
                not observations.get('participant_inventory')):
            raise ValueError('Missing complete participant inventory')
        actor_ids = [actor.get('actor_id') for actor in actors if isinstance(actor, dict)]
        if (len(actor_ids) != len(actors) or len(actor_ids) != len(set(actor_ids)) or
                any(type(actor_id) is not int for actor_id in actor_ids)):
            raise ValueError('Missing complete participant inventory')
        for actor in actors:
            body = actor.get('body_vertices_m')
            if (not isinstance(body, list) or len(body) < 4 or
                    any(not isinstance(v, list) or len(v) != 3 or
                        not all(finite_number(n) for n in v) for v in body)):
                raise ValueError('Missing complete participant body')
        if inventory_ids is None:
            inventory_ids = set(actor_ids)
        elif set(actor_ids) != inventory_ids:
            raise ValueError('Participant inventory changed during capture')
        previous_frame, previous_time = native, time_s
        current = []
        for role in ('ego', 'lead'):
            actor = row.get(role)
            if not isinstance(actor, dict):
                raise ValueError('Missing complete truck body: ' + role)
            actor_id = actor.get('actor_id')
            if type(actor_id) is not int or actor_id < 0:
                raise ValueError('Missing original truck identity: ' + role)
            current.append(actor_id)
            if actor.get('road_id') != context['road_id']:
                raise ValueError('Truck left sourced road')
            allowed = {context['lane_id']}
            if role == 'ego' and context.get('passing_lane_id') is not None:
                allowed.add(context['passing_lane_id'])
            if actor.get('lane_id') not in allowed:
                raise ValueError('Truck lane differs from original road context')
            body, velocity = actor.get('body_vertices_xy_m'), actor.get('velocity_mps')
            if (not isinstance(body, list) or len(body) < 4 or
                    any(not isinstance(v, list) or len(v) != 2 or
                        not all(finite_number(n) for n in v) for v in body) or
                    not isinstance(velocity, list) or len(velocity) != 3 or
                    not all(finite_number(n) for n in velocity) or
                    not finite_number(actor.get('overall_width_m')) or
                    actor['overall_width_m'] <= 0 or
                    not actor.get('blueprint_id')):
                raise ValueError('Missing complete truck body: ' + role)
        if current[0] == current[1]:
            raise ValueError('Truck roles share one actor identity')
        if not set(current) <= set(actor_ids):
            raise ValueError('Truck missing from original participant inventory')
        if ids is None:
            ids = current
        elif current != ids:
            raise ValueError('Original truck identity changed during capture')
    return {'frames': len(history), 'participant_ids': sorted(inventory_ids), 'truck_ids':ids,
            'sources': {name: digest(root/name) for name in
                        (*names, 'road_context.json', 'config.json', 'capture/evidence.jsonl')}}


def require_native_delivery(root, case_id):
    """Fail closed on fixtures and unreviewed captures.

    A future full delivery audit must additionally verify sealed originals,
    all traffic participants, decoded pixels, and physical completion before
    emitting an acceptance receipt.
    """
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    frames = config.get('rate_hz', 0) * config.get('duration_s', 0)
    joined = source_join(root, case_id, expected_frames=frames)
    for row in load_rows(root/'truck_history.jsonl'):
        if any(not row[role].get('overall_width_source') for role in ('ego', 'lead')):
            raise ValueError('Native truck width provenance missing')
    provenance = root / 'fixture-provenance.json'
    if provenance.exists():
        raise ValueError('Diagnostic fixture cannot establish Native delivery')
    result_path = root / 'result.json'
    if not result_path.is_file():
        raise ValueError('Missing Native result and physical completion')
    result = json.loads(result_path.read_text())
    if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Native non-diagnostic result required')
    raise ValueError('Independent pixel and physical completion audit is not yet implemented')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--source-selftest', action='store_true')
    parser.add_argument('--expected-frames', type=int)
    args = parser.parse_args()
    if args.source_selftest:
        if not args.expected_frames or args.expected_frames < 1:
            raise ValueError('Source selftest requires a positive expected frame count')
        print(json.dumps(source_join(args.attempt, args.case,
                                     expected_frames=args.expected_frames), sort_keys=True))
    else:
        require_native_delivery(args.attempt, args.case)


if __name__ == '__main__':
    main()
