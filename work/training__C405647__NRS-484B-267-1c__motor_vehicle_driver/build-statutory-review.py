"""Bind exact 1(c) source topics to selected CPU branches and pending originals."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    aid = HERE.name
    law_id = 'NRS-484B-267-1c'
    source_path = ROOT / 'inputs/coverage/branch-sources.json'
    assignment_path = ROOT / 'inputs' / aid / 'assignment.json'
    topics = read(source_path)['laws'][law_id]['topics']
    original = read(assignment_path)
    plan = read(HERE / 'case-plan.json')
    manifest = read(HERE / 'execution-manifest.json')
    if original['law']['text'] != plan['statutory_text'] or set(topics) != {'text-0','text-1','reviewed-scope-0'}:
        raise ValueError('Frozen 1(c) source inventory changed')
    ids = {x['case_id'] for x in plan['cases']}
    if ids != {x['case_id'] for x in manifest['cases']} or len(ids) != 6 or len(plan['comparisons']) != 3:
        raise ValueError('Six selected cases and three branch pairs required')
    directions = {x['branch']: x for x in plan['requirement_dispositions']}
    expected = {'authorized emergency approach and wait-until-passed',
                'law-enforcement-officer direction exception',
                'regulatory-agency official vehicle alternative'}
    if set(directions) != expected or any(x['status'] != 'selected_required' or len(x['case_ids']) != 2 for x in directions.values()):
        raise ValueError('Statutory alternatives or exception missing')
    public = HERE / 'current-public'
    evidence = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__',1)[-1]
        compatibility = public / (suffix + '-primary-compatibility.json')
        processing = public / (suffix + '-primary-processing.json')
        if not read(compatibility)['passed'] or not read(processing)['passed']:
            raise ValueError('Selected CPU receipt failed: ' + suffix)
        evidence.append({'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                         'compatibility_sha256': sha(compatibility), 'saved_sha256': sha(processing),
                         'original_native_observed': False})
    review = {'format': 'c405647-1c-statutory-branch-review-v1',
              'assignment_id': aid, 'law_id': law_id,
              'source_sha256': sha(source_path), 'assignment_sha256': sha(assignment_path),
              'plan_sha256': sha(HERE / 'case-plan.json'),
              'manifest_sha256': sha(HERE / 'execution-manifest.json'),
              'topics': [{'topic_id': key, 'text_sha256': hashlib.sha256(value['text'].encode()).hexdigest(),
                          'original_evidence_pending': 'Vehicle authority, qualifying flashing lamps, officer direction, whole-body passage and source pixels'}
                         for key,value in topics.items()],
              'selected_branches': list(directions), 'selected_evidence': evidence,
              'original_native_observed': False, 'physical_acceptance': False,
              'legal_verdict': None}
    target = HERE / 'statutory-branch-review.json'
    target.write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps({'topics': len(review['topics']), 'selected_cases': len(evidence), 'sha256': sha(target)}))

if __name__ == '__main__':
    main()
