"""Bind the exact referral text to supplied same-cell source assignments."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / 'inputs' / HERE.name / 'assignment.json'
    assignment = json.loads(source.read_text())
    referrals = []
    for suffix in ('1a', '1b', '1c'):
        path = ROOT / 'inputs' / (
            'training__C405647__NRS-484B-267-' + suffix + '__motor_vehicle_driver'
        ) / 'assignment.json'
        item = json.loads(path.read_text())
        if item['cell_id'] != assignment['cell_id'] or item['actor'] != assignment['actor']:
            raise ValueError('Same-cell subsection 1 source differs')
        referrals.append({'law_id': item['law_id'], 'source': item['law']['source'],
                          'text': item['law']['text'],
                          'input': path.relative_to(ROOT).as_posix(),
                          'sha256': digest(path)})
    review = {
        'format': 'c405647-2f-source-bound-statutory-review-v1',
        'assignment_id': assignment['assignment_id'],
        'target_source': {'path': source.relative_to(ROOT).as_posix(),
                          'sha256': digest(source), 'text': assignment['law']['text']},
        'approaches_referral': {'reference': 'NRS 484B.267(1)',
                                'supplied_same_cell_sources': referrals,
                                'measurement_boundary': 'Observe source-bound approach, yield, right-edge clearance and stop-until-passed separately; physical and legal outcomes require original review.'},
        'stops_referral': {'reference': 'NRS 484B.607',
                           'supplied_exact_law_text': False,
                           'measurement_boundary': 'Measure the stop and route the case to NRS 484B.607. Do not infer the unsupplied 607 duties or a compliance verdict.'},
        'activation': ['other motor-vehicle driver', 'authorized emergency or regulatory-agency official vehicle',
                       'moving or visibly preparing to move', 'qualifying flashing lights',
                       'subject approaches the vehicle'],
        'alternatives': ['emergency or official vehicle approaches the subject',
                         'emergency or official vehicle stops'],
        'exceptions': ['otherwise directed by law enforcement officer'],
        'preparation_indicators': ['visible vehicle movement', 'visible hand signal by its driver'],
        'not_legal_thresholds': ['speed requests in synthetic drafts', '20 Hz frame brackets'],
    }
    target = HERE / 'statutory-branch-review.json'
    target.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n')
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for row in referrals:
        if not any(source['path'] == row['input'] for source in plan['sources']):
            plan['sources'].append({'path': row['input'], 'sha256': row['sha256']})
    plan['source_observation_mapping'] = {
        term['term']: {
            'evidence': {
                'drv.responding_emergency': 'Original actor identity, authorization and qualifying lamp source review',
                'drv.approaching': 'Original opposing actor velocity, full body and separation time join',
                'rel.visible': 'Original four-camera pixels with independent sightline and visible preparation review',
                'drv.stopped': 'Original emergency velocity and body location time join',
                'rel.bearing': 'Original ego and emergency actor poses and headings',
                'kin.velocity': 'Original ego and emergency velocities and frame times',
                'dev.human_direction': 'Original officer direction or hand-signal context review and camera pixels',
            }[term['term']],
            'channels': [term['term']],
            'source_refs': [assignment['law']['source'], 'original vehicle_poses.jsonl',
                            'original video_frames.jsonl', 'original emergency_context.json'],
        } for term in assignment['source_observation_terms']
    }
    plan['source_context_review'] = (
        'Same-cell NRS 484B.267(1)(a), (b), and (c) supplied source text is bound in '
        'statutory-branch-review.json. NRS 484B.607 duties are not supplied; the stopped '
        'alternative must measure stop and preserve the referral without inferring its duty. '
        'Officer direction and visible preparation indicators require independent original sources.'
    )
    plan['runtime_uncertainties'] = [
        'Original emergency authorization, qualifying flashing-light equipment and pixels, '
        'driver visibility, officer direction, and Native motion remain unverified.',
        'NRS 484B.607 exact duties are not supplied; its stopped-vehicle referral is measured '
        'without a legal verdict.',
        'Subsection 1 duties are sourced from supplied same-cell assignments but physical '
        'yield, right-edge position, and stop-until-passed remain unverified.'
    ]
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'review_sha256': digest(target), 'supplied_referrals': len(referrals),
                      'unsupplied_referral': 'NRS 484B.607'}))


if __name__ == '__main__':
    main()
