"""Independent original-source checks for NRS 484B.127(2) delivery.

This module deliberately does not infer physical completion from a diagnostic.
The source checks can be exercised on diagnostic fixtures; delivery acceptance
requires a complete Native capture and the separate pixel/physical review.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED_CHECKS = ('native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


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


def pixel_checker(samples, width, height):
    """Require visible detail in every independently identified actor ROI."""
    by_frame = {}
    for row in samples:
        frame = row.get('video_frame')
        if type(frame) is not int or frame < 0:
            raise ValueError('Invalid pixel review frame')
        by_frame.setdefault(frame, []).append(row)
    seen = set()

    def check(frame):
        if (frame.width, frame.height) != (width, height):
            raise ValueError('Reviewed source dimensions changed')
        for row in by_frame.get(frame.index, []):
            box = row.get('bbox_xyxy')
            if not isinstance(box, list) or len(box) != 4 or any(type(n) is not int for n in box):
                raise ValueError('Missing reviewed actor pixel box')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and
                    (x1-x0)*(y1-y0) >= 16):
                raise ValueError('Reviewed actor pixel box outside source')
            colors = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = 3*(y*width+x)
                    colors.add(frame.pixels[offset:offset+3])
                    if len(colors) > 1:
                        break
                if len(colors) > 1:
                    break
            if len(colors) < 2:
                raise ValueError('Reviewed actor ROI has no visible pixel detail')
        if frame.index in by_frame:
            seen.add(frame.index)

    def finish():
        if seen != set(by_frame):
            raise ValueError('Reviewed actor pixel frame was not decoded')
    return check, finish


def media_module():
    repo = next((parent for parent in Path(__file__).resolve().parents
                 if (parent/'runtime/scenario_pipeline/worker_exchange/media.py').is_file()), None)
    if repo is None:
        raise ValueError('Pinned source media auditor unavailable')
    sys.path.insert(0, str(repo/'runtime/scenario_pipeline'))
    from worker_exchange import media
    return media


def require_native_delivery(root, case_id, job_id, attempt_number, recording_id,
                            review_path, output, decode_receipt, *, diagnostic_selftest=False):
    """Audit a complete original Native capture and write its acceptance receipt."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    review_path = Path(review_path).resolve()
    if (not root.is_dir() or output.name == 'result.json' or root not in output.parents
            or root in decode_receipt.parents or not job_id or not recording_id
            or type(attempt_number) is not int or attempt_number < 1):
        raise ValueError('Audit output or exact delivery identity invalid')
    config = json.loads((root/'config.json').read_text())
    if (not diagnostic_selftest and
            (config.get('rate_hz') != 20 or config.get('duration_s') != 45)):
        raise ValueError('Native delivery requires 20 Hz for 45 seconds')
    frames = (len(load_rows(root/'video_frames.jsonl')) if diagnostic_selftest else
              config.get('rate_hz', 0) * config.get('duration_s', 0))
    joined = source_join(root, case_id, expected_frames=frames)
    if not diagnostic_selftest and any(
            not row[role].get('overall_width_source')
            for row in load_rows(root/'truck_history.jsonl') for role in ('ego','lead')):
        raise ValueError('Native truck width provenance missing')
    if not diagnostic_selftest and (root/'fixture-provenance.json').exists():
        raise ValueError('Diagnostic fixture cannot establish Native delivery')
    result_path = root/'result.json'
    if not result_path.is_file():
        raise ValueError('Missing Native result and physical completion')
    result = json.loads(result_path.read_text())
    provenance = 'synthetic_fixture' if diagnostic_selftest else 'native'
    if (result.get('case_id') != case_id or result.get('provenance_kind') != provenance
            or result.get('diagnostic_fixture') is not diagnostic_selftest
            or result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Native non-diagnostic result required')
    seal_path = root/'capture-seal.json'
    seal = json.loads(seal_path.read_text())
    required = {'config.json','road_context.json','truck_history.jsonl',
                'capture/evidence.jsonl','trace.jsonl','video_frames.jsonl',
                *(name+'.mkv' for name in CAMERAS)}
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != provenance or
            seal.get('diagnostic_fixture') is not diagnostic_selftest or
            seal.get('frames') != frames or
            not required <= set(seal.get('sources', {}))):
        raise ValueError('Native capture seal incomplete')
    for name, value in seal['sources'].items():
        path = (root/name).resolve()
        if root not in path.parents or not path.is_file() or digest(path) != value:
            raise ValueError('Sealed original source changed: '+name)
    native_exit = root/'native-exit.json'
    if json.loads(native_exit.read_text()).get('capture_seal_sha256') != digest(seal_path):
        raise ValueError('Native exit does not bind capture seal')
    owner = json.loads((root/'owner-release.json').read_text())
    if owner.get('operator_attested') is not True or owner.get('native_exit_sha256') != digest(native_exit):
        raise ValueError('Owner release does not bind Native exit')
    physical = result.get('physical_checks', {})
    if not diagnostic_selftest and (physical.get('setup', {}).get('status') != 'met' or
            physical.get('maneuver', {}).get('status') != 'met' or
            not result.get('realized_observables')):
        raise ValueError('Physical completion absent from Native source assessment')
    sources = {name:root/(name+'.mkv') for name in CAMERAS}
    media = media_module()
    media.check_four_view_sources(sources)
    review = json.loads(review_path.read_text())
    if (review.get('case_id') != case_id or not review.get('reviewer') or
            not review.get('method') or
            review.get('frame_map_sha256') != joined['sources']['video_frames.jsonl'] or
            review.get('source_sha256') != {name:digest(path) for name,path in sources.items()}):
        raise ValueError('Independent pixel review source binding changed')
    observations = review.get('observations', [])
    if not observations or not set(joined['participant_ids']) <= {row.get('actor_id') for row in observations}:
        raise ValueError('Independent pixel review omits a participant')
    history = load_rows(root/'truck_history.jsonl')
    evidence = load_rows(root/'capture/evidence.jsonl')
    for item in observations:
        index = item.get('video_frame')
        if type(index) is not int or not 0 <= index < frames:
            raise ValueError('Pixel review frame differs from original source')
        actor_id, role = item.get('actor_id'), item.get('actor')
        known = {r['actor_id'] for r in evidence[index]['original_observations']['participants']}
        if (actor_id not in known or
                (role in ('ego','lead') and history[index][role]['actor_id'] != actor_id) or
                role not in ('ego','lead','other')):
            raise ValueError('Pixel review actor identity differs from original source')
    auditor_sha = digest(Path(__file__))
    for name, path in sources.items():
        sample = [row for row in observations if row.get('camera') == name]
        if not sample:
            raise ValueError('Independent pixel review omits camera: '+name)
        check, finish = pixel_checker(sample, *SIZES[name])
        media.audit(path, frames, checkers={'reviewed_actor_pixels':(auditor_sha,check)},
                    mapping_sha256=joined['sources']['video_frames.jsonl'])
        finish()
    raw = root/'raw.mkv'
    decoded = media.audit(raw, frames,
                          mapping_sha256=joined['sources']['video_frames.jsonl'],
                          receipt=decode_receipt)
    converted = root/'converted/trace.json'
    scenes = json.loads(converted.read_text())['scenes']
    mapping = load_rows(root/'video_frames.jsonl')
    if len(scenes) != frames or any(scene.get('t') != round(row['time_s']*1000)
                                   for scene,row in zip(scenes,mapping)):
        raise ValueError('Core trace/original frame time join differs')
    audit = {'format':'worker-delivery-audit-diagnostic' if diagnostic_selftest else 'worker-delivery-audit',
             'passed':not diagnostic_selftest,'software_checks_passed':True,
             'physical_acceptance_claimed':False,'diagnostic_fixture':diagnostic_selftest,
             'case_id':case_id,'job_id':job_id,'attempt':attempt_number,
             'recording_id':recording_id,
             'checks':{name:(not diagnostic_selftest if name in ('native_source','physical_completion','actual_pixels') else True)
                       for name in REQUIRED_CHECKS},'frames':frames,
             'source_result_sha256':digest(result_path),'video':'raw.mkv',
             'video_sha256':digest(raw),'trace':'converted/trace.json',
             'trace_sha256':digest(converted),'auditor_path':str(Path(__file__).resolve()),
             'auditor_sha256':auditor_sha,
             'source_decode_receipt_path':str(decode_receipt),
             'source_decode_receipt_sha256':digest(decode_receipt),
             'source_decode_auditor_sha256':decoded['auditor_sha256'],
             'original_sources':joined,'pixel_review_sha256':digest(review_path)}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(audit,indent=2)+'\n')
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--source-selftest', action='store_true')
    parser.add_argument('--expected-frames', type=int)
    parser.add_argument('--job-id')
    parser.add_argument('--attempt-number',type=int)
    parser.add_argument('--recording-id')
    parser.add_argument('--pixel-review',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--decode-receipt',type=Path)
    parser.add_argument('--diagnostic-selftest',action='store_true')
    args = parser.parse_args()
    if args.source_selftest:
        if not args.expected_frames or args.expected_frames < 1:
            raise ValueError('Source selftest requires a positive expected frame count')
        print(json.dumps(source_join(args.attempt, args.case,
                                     expected_frames=args.expected_frames), sort_keys=True))
    else:
        print(json.dumps(require_native_delivery(args.attempt,args.case,args.job_id,
                         args.attempt_number,args.recording_id,args.pixel_review,
                         args.output,args.decode_receipt,
                         diagnostic_selftest=args.diagnostic_selftest),sort_keys=True))


if __name__ == '__main__':
    main()
