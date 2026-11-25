"""Independent saved-distance comparison; reports observations, never a legal verdict."""
import argparse
import json
import math
from pathlib import Path

from crosswalk_measure import ASSIGNMENT, FRAMES, TWENTY_FEET_M


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit(far, near):
    ids = [ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2']
    for label, report, case_id in zip(('far', 'near'), (far, near), ids):
        _require(report.get('case_id') == case_id, label + ' exact case identity missing')
        _require(report.get('assignment_id') == ASSIGNMENT, label + ' assignment differs')
        _require(report.get('source_kind') == 'native_saved_sample', label + ' original Native source missing')
        _require(report.get('frame_count') == FRAMES and report.get('duration_s') == 30,
                 label + ' full duration missing')
        _require(report.get('camera_frame_map_validated') is True,
                 label + ' four-camera frame join missing')
        _require(report.get('video_pixels_decoded') is True,
                 label + ' decoded video proof missing')
        _require(report.get('legal_result') is None, label + ' legal outcome asserted by software')
        _require(isinstance(report.get('original_source_sha256'), dict) and
                 set(report['original_source_sha256']) ==
                 {'vehicle-poses.jsonl', 'video_frames.jsonl', 'crosswalk-inventory.json', 'control-intent.jsonl'},
                 label + ' original source hashes missing')
        _require(all(isinstance(v, str) and len(v) == 64 for v in report['original_source_sha256'].values()),
                 label + ' original source hash invalid')
        _require(isinstance(report.get('independent_source_review_sha256'), str) and
                 len(report['independent_source_review_sha256']) == 64,
                 label + ' independent source review missing')
        _require(report.get('independent_source_review_findings', {}).get('marked_crosswalk_source_id') == 'present',
                 label + ' marked crosswalk unestablished')
        _require(len(report.get('body_to_crosswalk_m_by_frame', [])) == FRAMES,
                 label + ' full body-distance sequence missing')
        _require(len(report.get('center_to_crosswalk_m_by_frame', [])) == FRAMES,
                 label + ' full center-distance sequence missing')
        _require(report.get('halt_proxy_spans'), label + ' no observed halt span')
        _require(report.get('control_frame_join_validated') is True,
                 label + ' original control/pose join missing')
    for field in ('crosswalk_rect_xyxy_m', 'marked_crosswalk_source_id',
                  'crosswalk_extent_source_id'):
        _require(far.get(field) == near.get(field), 'fixed crosswalk condition differs: ' + field)
    _require(far.get('statutory_20_feet_m') == near.get('statutory_20_feet_m') == TWENTY_FEET_M,
             'statutory distance conversion differs')
    _require(far['independent_source_review_findings'] == near['independent_source_review_findings'],
             'fixed source review findings differ')
    _require(far.get('engineering_action') == 'controlled_1' and
             near.get('engineering_action') == 'controlled_2',
             'declared parking action controls differ')
    distances = []
    for label, report in (('far', far), ('near', near)):
        frames = report.get('halt_proxy_frames')
        _require(isinstance(frames, list) and frames and
                 all(isinstance(i, int) and 0 <= i < FRAMES for i in frames),
                 label + ' halt frame identities invalid')
        values = [report['body_to_crosswalk_m_by_frame'][i] for i in frames]
        _require(all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in values),
                 label + ' body distance invalid')
        distances.append(min(values))
    _require(distances[0] > distances[1], 'declared distance difference not observed')
    return {'format': 'c229397-comparison-audit-v1', 'assignment_id': ASSIGNMENT,
            'case_ids': ids, 'minimum_halt_body_distance_m': distances,
            'farther_case_observed': True, 'fixed_crosswalk_source_review': True,
            'legal_result': None, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--far', required=True)
    parser.add_argument('--near', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.far).read_text()),
                           json.loads(Path(args.near).read_text())), sort_keys=True))
