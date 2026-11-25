"""Independent diagnostic delivery and controlled-context audit for qualifiers."""
import argparse
import hashlib
import json
from pathlib import Path

from qualifier_source_audit import ASSIGNMENT, audit as source_audit


CASES = {'traffic_conflict_near': ('traffic_conflict', 'traffic-actors.jsonl'),
         'law_compliance_near': ('law_compliance', 'authority-events.jsonl'),
         'police_direction_near': ('police_direction', 'authority-events.jsonl'),
         'device_direction_near': ('device_direction', 'device-states.jsonl')}
BASE_SOURCES = ('vehicle-poses.jsonl', 'control-intent.jsonl', 'video_frames.jsonl',
                'crosswalk-inventory.json', 'crosswalk-source-review.json',
                'trace.jsonl', 'qualifier-context.json', 'qualifier-source-packet.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines()]


def audit(case, attempt, processing_path, baseline, diagnostic=False, review_path=None):
    attempt, baseline = Path(attempt).resolve(), Path(baseline).resolve()
    suffix = case.removeprefix(ASSIGNMENT + '__')
    if case != ASSIGNMENT + '__' + suffix or suffix not in CASES:
        raise ValueError('Exact qualifier case differs')
    qualifier, context_file = CASES[suffix]
    processing = json.loads(Path(processing_path).read_text())
    if not all((processing.get('format') == 'worker-saved-processing',
                processing.get('case_id') == case, processing.get('passed') is True,
                processing.get('recorded_only') is True,
                processing.get('originals_preserved') is True,
                processing.get('missing_evidence') is False,
                processing.get('physical_acceptance_claimed') is False,
                processing.get('legal_acceptance_claimed') is False)):
        raise ValueError('Qualifier saved processing receipt differs')
    hashes = processing.get('original_source_hashes', {})
    for name in (*BASE_SOURCES, context_file):
        if not (attempt / name).is_file() or hashes.get(name) != sha(attempt / name):
            raise ValueError('Qualifier original source missing or changed: ' + name)
    source = source_audit(attempt, attempt / 'qualifier-source-packet.json',
                          case, qualifier, diagnostic=diagnostic)
    if source['finding'] != 'unresolved' or source['legal_verdict'] is not None:
        raise ValueError('Qualifier source has unsupported determination')
    poses, frame_map, controls, context = (rows(attempt / name) for name in (
        'vehicle-poses.jsonl', 'video_frames.jsonl', 'control-intent.jsonl', context_file))
    if not all(len(items) == 600 for items in (poses, frame_map, controls, context)):
        raise ValueError('Qualifier subject stream incomplete')
    for index, (pose, frame, control, item) in enumerate(zip(
            poses, frame_map, controls, context)):
        if not (pose['video_frame'] == control['video_frame'] == item['video_frame'] == index and
                pose['native_frame'] == control['native_frame'] == item['native_frame'] == frame['native_frame']):
            raise ValueError('Qualifier original frame join differs')
    if sha(attempt / 'crosswalk-inventory.json') != sha(baseline / 'crosswalk-inventory.json') or sha(
            attempt / 'crosswalk-source-review.json') != sha(baseline / 'crosswalk-source-review.json'):
        raise ValueError('Controlled crosswalk context differs')
    result_path = Path(processing.get('result', ''))
    if not result_path.is_file() or sha(result_path) != processing.get('result_sha256'):
        raise ValueError('Qualifier saved result missing or changed')
    result = json.loads(result_path.read_text())
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Qualifier diagnostic result crossed acceptance boundary')
    if diagnostic and result.get('maneuver_completed') is not False:
        raise ValueError('Synthetic qualifier claimed physical completion')
    decoded = processing.get('final_video_checks', {})
    if decoded.get('passed') is not True or decoded.get('frames') != 600:
        raise ValueError('Qualifier final video decode incomplete')
    if suffix == 'traffic_conflict_near':
        if len({item.get('actor_id') for item in context}) != 1 or all(
                item.get('speed_mps', 0) == 0 for item in context):
            raise ValueError('Distinct traffic actor motion missing')
        difference = 'second_actor_trajectory'
    elif suffix == 'device_direction_near':
        if not all('device_present' in item and 'state' in item for item in context):
            raise ValueError('Native device state or absence not inventoried')
        difference = 'device_state_or_explicit_absence'
    else:
        if not all(item.get('qualifier') == qualifier and
                   item.get('authority_status') == 'unverified' for item in context):
            raise ValueError('Source-gated authority timeline missing')
        if suffix == 'police_direction_near' and len({item.get(
                'candidate_participant_id') for item in context}) != 1:
            raise ValueError('Direction participant identity differs')
        difference = 'source_gated_' + qualifier + '_timeline'
    physical_review_complete = False
    if not diagnostic:
        if review_path is None:
            raise ValueError('Independent original qualifier physical review required')
        review = json.loads(Path(review_path).read_text())
        expected = {name: hashes[name] for name in (*BASE_SOURCES, context_file)}
        if (review.get('format') != 'c229397-original-qualifier-physical-review-v1' or
                review.get('case_id') != case or review.get('source_sha256') != expected or
                review.get('processing_sha256') != sha(processing_path) or
                review.get('actual_pixels_reviewed') is not True or
                review.get('marked_crosswalk_reviewed') is not True or
                review.get('qualifier_context_visible') is not True or
                review.get('physical_completion_reviewed') is not True or
                result.get('maneuver_completed') is not True):
            raise ValueError('Original qualifier physical review incomplete or stale')
        physical_review_complete = True
    return {'format': 'c229397-qualifier-delivery-audit-v1', 'case_id': case,
            'diagnostic_fixture': diagnostic, 'qualifier': qualifier,
            'source_audit_sha256': sha(attempt / 'qualifier-source-packet.json'),
            'controlled_baseline_case': ASSIGNMENT + '__controlled_2',
            'controlled_difference': difference,
            'frame_join_count': 600, 'final_video_decoded': True,
            'physical_preparation': 'source_shapes_checked; original motion and pixels pending'
                if diagnostic else 'independent original motion and pixels reviewed',
            'physical_review_complete': physical_review_complete,
            'finding': 'unresolved', 'physical_acceptance_claimed': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--review')
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.case, args.attempt, args.processing, args.baseline,
                  args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value, sort_keys=True))
