"""Map every frozen law observation prompt to source-backed capture evidence."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = f'inputs/{HERE.name}/assignment.json'
REVIEW = f'inputs/{HERE.name}/review-context/review.json'


def main() -> None:
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    channels = {
        'ru.truck': (['ego_body_pose', 'lead_body_pose'],
                     'Read both original Native body identities and truck blueprints; actual vehicle class still needs local review.'),
        'ru.trailer_or_combination': (['ego_body_pose', 'lead_body_pose'],
                                     'Retain separate subject and lead blueprint/body sources so a combination can be classified if observed.'),
        'kin.extent': (['ego_body_pose', 'lead_body_pose'],
                       'Measure each original truck body vertex span against the 80-inch class boundary.'),
        'drv.following': (['ego_body_pose', 'lead_body_pose', 'surface_gap_m'],
                          'Join full body positions, lane identity and road-arc gap throughout the 600-frame following window.'),
        'rel.surface_gap': (['surface_gap_m'],
                            'Recompute original full-body road-surface clearance continuously against 152.4 m.'),
        'rel.ahead_behind_in_lane': (['ego_body_pose', 'lead_body_pose'],
                                    'Join both original lane and body positions to establish subject behind lead.'),
        'drv.laned_roadway': (['ego_body_pose'],
                             'Survey authored road lane sections and later original highway context; lane identity comes from Native.'),
        'st.lane_adjacency': (['ego_body_pose'],
                             'Read the original map lane sections at the subject track and count same-direction lanes.'),
        'drv.overtaking': (['ego_body_pose', 'lead_body_pose'],
                           'Measure subject lane departure, truck clearance, lead pass and return from joined original bodies.')}
    terms = {item['term'] for item in json.loads((ROOT / INPUT).read_text())['source_observation_terms']}
    if set(channels) != terms:
        raise ValueError('Frozen law observation terms changed')
    plan['source_observation_mapping'] = {
        term: {'evidence': evidence, 'channels': names,
               'source_refs': [INPUT, REVIEW, 'native/runner.py', 'native/finalize.py']}
        for term, (names, evidence) in channels.items()}
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'reason': 'Source-bound original Native and four-camera frame join used by the selected finalizer'}
        for name in ('ego_body_pose', 'lead_body_pose', 'surface_gap_m', 'camera_frame_join')]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'subject and lead truck bodies across the hill crest', 'interval': '0-30 s'},
            {'view': 'approach', 'subject': 'subject approach and following lane', 'interval': '0-30 s'},
            {'view': 'reference_corner', 'subject': 'lead truck body and road-lane reference', 'interval': '0-30 s'},
            {'view': 'driver_reference', 'subject': 'subject truck and opposing-lane context', 'interval': '0-30 s'}],
        'physical_limit': 'CPU fixtures test frame joins and decode; original pixels and body visibility require local review.'}
    gaps = [
        {'id': 'gap_500ft_continuous', 'requirement': 'Continuous measured qualified-truck space on both sides of 500 ft',
         'source': REVIEW, 'why_existing_insufficient': 'Frozen requests list 149.352, 152.4 and 155.448 m but do not expose original joined body traces or a source-hashed equivalence receipt here.'},
        {'id': 'two_lane_exception', 'requirement': 'Two or more lanes available in the subject direction',
         'source': REVIEW, 'why_existing_insufficient': 'One accepted two-lane membership is listed without local map and body sources needed to prove this controlled exception.'},
        {'id': 'passing_carveout', 'requirement': 'Subject passing versus holding behind a qualified truck',
         'source': REVIEW, 'why_existing_insufficient': 'Prior passing requests lack local original trajectories and clearance receipts for this exact pair.'},
        {'id': 'conditions_permit', 'requirement': 'Lead braking and road conditions affecting a 500-foot space',
         'source': INPUT, 'why_existing_insufficient': 'The frozen review gives no local source-hashed controlled lead-braking comparison; legal conditions remain unresolved.'}]
    plan['evidence_review'] = {
        'method': 'Reviewed frozen assignment membership and review-context request summaries; no accepted original source copies are present in this worker checkout.',
        'reviewer': 'C102372 CPU preparation owner',
        'facts': [], 'gaps': gaps,
        'limitation': 'Accepted membership and request descriptions are not realized equivalence or statutory findings.'}
    for case in plan['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        gap = ('passing_carveout' if suffix.startswith('passing_') else
               'conditions_permit' if suffix.startswith('conditions_') else
               'two_lane_exception' if suffix == 'two_lane_exception' else
               'gap_500ft_continuous')
        case['gap_ids'] = [gap]
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'mapped_terms': len(channels), 'evidence_gaps': len(gaps),
                      'planned_cases': len(plan['cases'])}, sort_keys=True))


if __name__ == '__main__':
    main()
