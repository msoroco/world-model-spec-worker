import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE / 'case-plan.json'
plan = json.loads(path.read_text())
coverage = [
    ('overview', 'full mountain-road encounter, ego and blind person'),
    ('approach', 'ego approach, person and contact region'),
    ('reference_corner', 'cane marker or assistant and pedestrian clearance'),
    ('driver_reference', 'driver view of person and stop/release region'),
]
plan['camera_plan'] = {
    'profile': 'overview1080-capability',
    'duration_s': 30,
    'composition': 'synchronized_four_view_primary',
    'coverage': [{'view': view, 'subject': subject, 'interval': 'all 600 frames'}
                 for view, subject in coverage],
}
old = plan['source_observation_mapping']
assert isinstance(old, list)
plan['source_observation_mapping'] = {
    row['term']: {
        'evidence': row['measurement'] + '; ' + row['evidence_boundary'] + '; original Native review pending',
        'channels': [row['term']],
        'source_refs': ['vehicle-person-poses.jsonl', 'blind-person-context.json',
                        'road-survey.json', 'four original camera videos'],
    }
    for row in old
}
path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
print(len(plan['source_observation_mapping']), len(plan['camera_plan']['coverage']))
