"""CPU test of proposed red-curb delivery audit; no physical acceptance claim."""
import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from delivery_audit import (ASSIGNMENT, audit, lines, read, validate_rows,
                            validate_composition,
                            validate_review, pixel_checker, sha)


ROOT = Path(__file__).resolve().parents[3]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def reject(call, message):
    try:
        call()
    except ValueError as error:
        assert message in str(error), (message, str(error))
        return
    raise AssertionError('audit accepted invalid: ' + message)


def sources(slug):
    p = ROOT / '.runtime-work' / ('c150142-merged-' + slug + '-primary-compat-v1')
    return (p, lines(p / 'native-raw-actors.jsonl'),
            lines(p / 'video_frames.jsonl'), lines(p / 'trace.jsonl'),
            read(p / 'native-map-readback.json'))


def main():
    observations = {}
    for slug in ('reference', 'contrast'):
        p, raw, frames, trace, map_readback = sources(slug)
        case = ASSIGNMENT + '__' + slug
        observed = validate_rows(raw, frames, trace, map_readback, case, 240,
                                 'synthetic_native_sample')
        composition = read(p / 'four-view-receipt.json')
        validate_composition(composition, p, (p / 'raw.mkv').resolve(), 240)
        changed_composition = copy.deepcopy(composition)
        changed_composition['sources']['overview'] = '0' * 64
        reject(lambda: validate_composition(changed_composition, p,
                                            (p / 'raw.mkv').resolve(), 240),
               'four-view source binding differs')
        assert observed['red_curb_stop_or_park_observed'] == (slug == 'reference')
        observations[slug] = observed
        changed = copy.deepcopy(frames)
        changed[20]['native_frame'] += 1
        reject(lambda: validate_rows(raw, changed, trace, map_readback, case, 240,
                                     'synthetic_native_sample'), 'join differs')
        changed = copy.deepcopy(raw)
        changed[20]['source_kind'] = 'original_native'
        reject(lambda: validate_rows(changed, frames, trace, map_readback, case, 240,
                                     'synthetic_native_sample'), 'join differs')
        changed = copy.deepcopy(raw)
        changed[20]['time_s'] += 0.1
        reject(lambda: validate_rows(changed, frames, trace, map_readback, case, 240,
                                     'synthetic_native_sample'), 'join differs')
        changed = copy.deepcopy(map_readback)
        changed['paint_color'] = 'white'
        reject(lambda: validate_rows(raw, frames, trace, changed, case, 240,
                                     'synthetic_native_sample'), 'red-paint readback')
        reject(lambda: validate_rows(raw, frames, trace, map_readback,
                                     ASSIGNMENT + '__other', 240,
                                     'synthetic_native_sample'), 'exact case')
        with tempfile.TemporaryDirectory(prefix='c150142-audit-', dir='.runtime-work') as tmp:
            folder = Path(tmp)
            reject(lambda: audit(case, 1, 1, p.parent.name, p,
                                 folder / 'review.json', p / 'raw.mkv',
                                 folder / 'decode.json', p / 'audit.json'),
                   'result provenance differs')
        review = {'source_kind': 'original_native_review', 'case_id': case,
                  'candidate_id': 'primary', 'reviewer_id': 'cpu-test-reviewer',
                  'painted_curb_visible': True, 'ego_body_visible': True,
                  'original_motion_reviewed': True,
                  'jurisdiction_and_signage_reviewed': True,
                  'legal_verdict': None,
                  'sources': {name: sha(p / name) for name in
                              ('native-raw-actors.jsonl', 'native-map-readback.json',
                               'video_frames.jsonl', 'trace.jsonl', 'config.json',
                               'result.json', 'raw.mkv',
                               *(view + '.mkv' for view in VIEWS))},
                  'pixel_boxes': [
                      {'claim': 'ego_body', 'frame': 0, 'rect_xywh': [0, 0, 2, 2]},
                      {'claim': 'red_paint', 'frame': 1, 'rect_xywh': [2, 0, 2, 2]}]}
        boxes = validate_review(review, case, 'primary', p, p / 'raw.mkv')
        callback, seen = pixel_checker(boxes, 240)
        callback(SimpleNamespace(index=0, width=4, height=2,
                                 pixels=bytes(range(24))))
        callback(SimpleNamespace(index=1, width=4, height=2,
                                 pixels=bytes(range(24))))
        assert seen == {'ego_body', 'red_paint'}
        changed = copy.deepcopy(review)
        changed['sources']['raw.mkv'] = '0' * 64
        reject(lambda: validate_review(changed, case, 'primary', p, p / 'raw.mkv'),
               'source hash differs')
        changed = copy.deepcopy(review)
        changed['pixel_boxes'] = changed['pixel_boxes'][:1]
        reject(lambda: validate_review(changed, case, 'primary', p, p / 'raw.mkv'),
               'pixel claims')
        changed = copy.deepcopy(review)
        changed['pixel_boxes'][1]['frame'] = 0
        changed['pixel_boxes'][1]['rect_xywh'] = [0, 0, 2, 2]
        reject(lambda: pixel_checker(changed['pixel_boxes'], 240), 'reuse one box')
        callback, _ = pixel_checker(boxes, 240)
        reject(lambda: callback(SimpleNamespace(index=0, width=4, height=2,
                                                pixels=bytes(24))), 'box is flat')
    print(json.dumps({'format': 'c150142-delivery-audit-cpu-proof-v1',
                      'diagnostic_pairs': list(observations),
                      'row_count': {k: v['frames'] for k, v in observations.items()},
                      'rejected': ['stale_composition', 'frame_join', 'source_provenance', 'time_join',
                                   'wrong_paint', 'wrong_case', 'synthetic_delivery',
                                   'stale_review_hash', 'missing_pixel_claim',
                                   'reused_box', 'flat_pixels'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
