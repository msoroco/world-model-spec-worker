"""Exercise the independent comparison audit with changed and missing evidence."""
import copy
import json

from comparison_audit import audit
from crosswalk_measure import measure
from prove_crosswalk import encoded, sample


def report(suffix, x):
    packet, inventory = sample(x)
    result = measure(encoded(packet), encoded(inventory))
    result.update(case_id=result['assignment_id'] + '__' + suffix,
                  source_kind='native_saved_sample', camera_frame_map_validated=True,
                  video_pixels_decoded=True, independent_source_review_sha256='a' * 64,
                  control_frame_join_validated=True, engineering_action=suffix,
                  independent_source_review_findings={'marked_crosswalk_source_id': 'present'},
                  original_source_sha256={name: 'b' * 64 for name in
                      ('vehicle-poses.jsonl', 'video_frames.jsonl', 'crosswalk-inventory.json',
                       'control-intent.jsonl')})
    return result


def reject(far, near, expected):
    try:
        audit(far, near)
    except ValueError as exc:
        if str(exc) == expected:
            return
        raise
    raise RuntimeError('invalid comparison accepted: ' + expected)


def main():
    far, near = report('controlled_1', -14), report('controlled_2', -5)
    good = audit(far, near)
    if good['minimum_halt_body_distance_m'] != [12, 3] or good['legal_result'] is not None:
        raise ValueError('comparison values or legal reservation differ')
    bad = copy.deepcopy(near)
    bad['crosswalk_rect_xyxy_m'][0] = 1
    reject(far, bad, 'fixed crosswalk condition differs: crosswalk_rect_xyxy_m')
    bad = copy.deepcopy(near)
    bad['original_source_sha256'] = {}
    reject(far, bad, 'near original source hashes missing')
    bad = copy.deepcopy(near)
    bad['video_pixels_decoded'] = False
    reject(far, bad, 'near decoded video proof missing')
    bad = copy.deepcopy(near)
    bad['body_to_crosswalk_m_by_frame'] = far['body_to_crosswalk_m_by_frame']
    reject(far, bad, 'declared distance difference not observed')
    bad = copy.deepcopy(near)
    bad['case_id'] = far['case_id']
    reject(far, bad, 'near exact case identity missing')
    print(json.dumps({'passed': True, 'far_body_gap_m': 12, 'near_body_gap_m': 3,
                      'checks': ['fixed crosswalk rejection', 'missing original source rejection',
                                 'missing video decode rejection', 'absent distance change rejection',
                                 'case identity rejection'], 'legal_result': None}, sort_keys=True))


if __name__ == '__main__':
    main()
