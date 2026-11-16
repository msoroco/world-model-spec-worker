"""Independent proposed audit for an original C135709 stand delivery.

CPU diagnostics may exercise mechanics, but only an original Native attempt with
source-bound human pixel review can produce a passing delivery receipt.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
CLAIMS = {'vehicle_body', 'stand_sign', 'stand_polygon'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    path = Path(path)
    require(path.is_file(), 'Missing delivery source: '+str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read(path):
    path = Path(path)
    require(path.is_file(), 'Missing delivery source: '+str(path))
    return json.loads(path.read_text())


def validate_rows(actors, frames, trace, reviews, *, source_kind):
    require(len(actors) == len(frames) == len(trace) == len(reviews) == 240,
            'Original actor/frame/trace/review count differs')
    first = actors[0].get('native_frame')
    require(type(first) is int, 'Original Native frame identity absent')
    source_speed = ('original_native' if source_kind == 'original_native'
                    else 'synthetic_native_sample')
    review_kind = ('human_frame_review' if source_kind == 'original_native'
                   else 'synthetic_cpu')
    for i, (actor, frame, point, review) in enumerate(zip(actors, frames, trace, reviews)):
        ego = actor.get('ego', {})
        t = actor.get('time_s')
        require(actor.get('frame') == review.get('frame') == i and
                actor.get('native_frame') == frame.get('native_frame') ==
                frame.get('carla_frame') == review.get('native_frame') ==
                point.get('frame') == first+i and
                frame.get('video_frame') == i and
                actor.get('source_kind') == review.get('source_kind') == source_kind and
                actor.get('speed_source') == source_speed and
                review.get('review_provenance') == review_kind and
                type(t) in (int, float) and math.isfinite(t) and
                all(abs(other.get('time_s', -999)-t) < 1e-5
                    for other in (frame, point, review)) and
                point.get('position_m') == ego.get('center_native_xyz_m') and
                point.get('speed_mps') == ego.get('speed_mps') and
                actor.get('observed_road_id') == 517 and
                actor.get('observed_lane_id') in (-1, -2) and
                ego.get('actor_id') is not None and
                isinstance(ego.get('body_native_xyz_m'), list) and
                len(ego['body_native_xyz_m']) == 8 and
                type(ego.get('speed_mps')) in (int, float) and
                math.isfinite(ego['speed_mps']) and ego['speed_mps'] >= 0,
                'Original actor/frame/trace/review join differs at '+str(i))
    return {'frames': 240, 'first_native_frame': first,
            'last_native_frame': first+239}


def pixel_checker(boxes):
    require(isinstance(boxes, list) and {x.get('claim') for x in boxes} >= CLAIMS,
            'Independent pixel review lacks vehicle, sign or stand polygon')
    seen = set()
    by_frame = {}
    for box in boxes:
        index, rect = box.get('frame'), box.get('rect_xywh')
        require(type(index) is int and 0 <= index < 240 and
                isinstance(rect, list) and len(rect) == 4 and
                all(type(n) is int for n in rect) and rect[2] >= 2 and rect[3] >= 2,
                'Invalid reviewed pixel box')
        by_frame.setdefault(index, []).append(box)

    def check(frame):
        for box in by_frame.get(frame.index, []):
            x, y, width, height = box['rect_xywh']
            require(0 <= x and 0 <= y and x+width <= frame.width and
                    y+height <= frame.height, 'Reviewed pixel box exceeds decoded video')
            samples = bytearray()
            for row in range(y, y+height):
                start = (row*frame.width+x)*3
                samples.extend(frame.pixels[start:start+width*3])
            require(samples and max(samples) > min(samples),
                    'Reviewed pixel box is flat')
            seen.add(box['claim'])
    return check, seen


def media_module():
    for parent in Path(__file__).resolve().parents:
        location = parent/'runtime/pipeline'
        if (location/'scenario_pipeline/worker_exchange/media.py').is_file():
            sys.path.insert(0, str(location))
            from scenario_pipeline.worker_exchange import media
            return media
    raise ValueError('Pinned media auditor unavailable')


def audit_original(attempt, case, review_path, output, decode_receipt):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    require(not output.exists() and not Path(decode_receipt).exists(),
            'Retain prior independent audit; choose fresh outputs')
    config, result = read(attempt/'config.json'), read(attempt/'result.json')
    require(config.get('case_id') == result.get('case_id') == case and
            case.endswith(('__reference', '__contrast')) and
            result.get('provenance_kind') == 'original_native_unreviewed' and
            result.get('accepted') is False,
            'Synthetic or wrong-case result cannot establish original Native delivery')
    actors = rows(attempt/'native-raw-actors.jsonl')
    frames = rows(attempt/'video_frames.jsonl')
    trace = rows(attempt/'trace.jsonl')
    stand_reviews = rows(attempt/'stand-review.jsonl')
    joined = validate_rows(actors, frames, trace, stand_reviews,
                           source_kind='original_native')
    required = ('native-raw-actors.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                'stand-review.jsonl', 'native-map-readback.json', 'config.json',
                'result.json')
    sources = {name: sha(attempt/name) for name in required}
    sources.update({name+'.mkv': sha(attempt/(name+'.mkv')) for name in CAMERAS})
    review = read(review_path)
    require(review.get('case_id') == case and
            review.get('candidate_id') == config.get('candidate_id') and
            isinstance(review.get('reviewer_id'), str) and
            bool(review['reviewer_id'].strip()) and
            review.get('source_kind') == 'original_native_review' and
            review.get('legal_verdict') is None and
            all(review.get('sources', {}).get(name) == value
                for name, value in sources.items()),
            'Independent original stand review or source hashes differ')
    physical = result.get('physical_checks', {}).get('maneuver', {})
    require(physical.get('status') == 'met' and
            result.get('maneuver_completed') is True and
            result.get('physical_failure_flags') == [] and
            all(physical.get('sources', {}).get(name) == sources[name]
                for name in ('native-raw-actors.jsonl', 'video_frames.jsonl',
                             'stand-review.jsonl', 'native-map-readback.json')) and
            physical.get('legal_verdict_claimed') is False,
            'Original physical completion missing or stale')
    media = media_module()
    media.check_four_view_sources({name: attempt/(name+'.mkv') for name in CAMERAS})
    check, seen = pixel_checker(review.get('pixel_boxes'))
    primary = attempt/'raw.mkv'
    decoded = media.audit(primary, 240,
                          checkers={'c135709_reviewed_pixels': (sha(Path(__file__)), check)},
                          mapping_sha256=sources['video_frames.jsonl'],
                          receipt=decode_receipt)
    require(CLAIMS <= seen, 'Full decode omitted reviewed visible features')
    receipt = {'format': 'c135709-original-delivery-audit-v1',
        'passed': True, 'case_id': case, 'candidate_id': config['candidate_id'],
        'checks': {name: True for name in CHECKS}, 'joined': joined,
        'sources': sources, 'review_sha256': sha(review_path),
        'decode_sha256': sha(decode_receipt),
        'rgb_sequence_sha256': decoded['rgb_sequence_sha256'],
        'original_native_observed': True, 'legal_verdict': None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt
