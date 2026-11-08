"""Bind LVMC 11.38.030 source topics to constructed CPU evidence without promoting readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-38-030'
CASES = tuple(AID + '__' + suffix for suffix in ('witness_1', 'witness_2'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def build():
    source_path = ROOT / 'inputs/coverage/branch-sources.json'
    assignment_path = ROOT / 'inputs' / AID / 'assignment.json'
    plan_path = HERE / 'case-plan.json'
    manifest_path = HERE / 'draft-execution-manifest.json'
    comparison_path = HERE / 'synthetic-controlled-comparison.json'
    context_path = HERE / 'native/context-proof.json'
    source = read(source_path)['laws'][LAW]
    plan, manifest = read(plan_path), read(manifest_path)
    comparison, context = read(comparison_path), read(context_path)
    if set(source['topics']) != {'text-0', 'reviewed-scope-0'}:
        raise ValueError('Exact source topic inventory changed')
    if source['law']['text'] != plan['source_law']['text']:
        raise ValueError('Exact municipal clause differs')
    if {c['case_id'] for c in plan['cases']} != set(CASES):
        raise ValueError('Witness case coverage differs')
    if {c['case_id'] for c in manifest['cases']} != set(CASES):
        raise ValueError('Exact bundle case coverage differs')
    if comparison['case_plan_sha256'] != sha(plan_path) or \
            comparison['manifest_sha256'] != sha(manifest_path):
        raise ValueError('Controlled comparison not bound to current plan')
    metrics = []
    for row in comparison['rows']:
        candidate = row['candidate_id']
        if len(row['negatives']) != 4 or not all(n['rejected'] for n in row['negatives']):
            raise ValueError('Controlled comparison tamper controls incomplete')
        for suffix in ('witness_1', 'witness_2'):
            context_row = next(p for p in context['positives']
                               if p['case_suffix'] == suffix and p['candidate_id'] == candidate)
            measured = read(HERE / 'native/context-fixtures' / suffix /
                            candidate / 'context-measurement.json')
            occupancy = read(HERE / 'native/saved-fixtures' / suffix /
                             candidate / 'analysis-report.json')
            if (measured['city_authority_reviewed'] is not False or
                    measured['driveway_rule_composition_reviewed'] is not False or
                    measured['legal_verdict'] is not None):
                raise ValueError('Synthetic geometry claimed statutory conclusion')
            metrics.append({'case_id': AID + '__' + suffix, 'candidate_id': candidate,
                            'moving_sidewalk_overlap_frames': row['positive'][
                                'roadway_overlap_frames' if suffix == 'witness_1' else
                                'sidewalk_overlap_frames'],
                            'full_body_inside_sidewalk_frames': occupancy[
                                'full_body_inside_sidewalk_frames'],
                            'moving_sidewalk_intersection_frames': measured[
                                'moving_sidewalk_intersection_frames'],
                            'candidate_city_sidewalk_non_driveway_frames':
                                context_row['candidate_frames'],
                            'context_measurement_sha256': sha(HERE / 'native/context-fixtures' /
                                                              suffix / candidate / 'context-measurement.json')})
    review = {'format': 'c422978-source-to-physical-branch-review-v1',
              'assignment_id': AID, 'law_id': LAW,
              'source_hashes': {'assignment.json': sha(assignment_path),
                                'branch-sources.json': sha(source_path),
                                'case-plan.json': sha(plan_path),
                                'draft-execution-manifest.json': sha(manifest_path),
                                'synthetic-controlled-comparison.json': sha(comparison_path),
                                'native/context-proof.json': sha(context_path)},
              'topic_ids': sorted(source['topics']),
              'branch': 'Motorcycle riding upon a sidewalk',
              'case_ids': list(CASES),
              'comparison_ids': [plan['comparisons'][0]['comparison_id']],
              'statutory_elements': [
                  {'element': 'motorcycle or motor scooter',
                   'saved_observable': 'motorcycle_blueprint and original actor identity',
                   'original_status': 'unverified'},
                  {'element': 'ridden upon a sidewalk',
                   'saved_observable': 'moving motorcycle body versus Native sidewalk polygon',
                   'original_status': 'unverified'},
                  {'element': 'of the City',
                   'saved_observable': 'source-bound city boundary and Native-to-city transform',
                   'original_status': 'unverified'},
                  {'element': 'driveway crossing composition',
                   'saved_observable': 'source-bound driveway crossing footprint and rule review',
                   'original_status': 'unverified'}],
              'synthetic_candidate_metrics': metrics,
              'synthetic_negative_count': 16,
              'status': 'cpu_constructed_pending_original_and_legal_review',
              'runnable_branch_claimed': False, 'city_authority_claimed': False,
              'legal_verdict_claimed': False}
    output = HERE / 'statutory-branch-review.json'
    output.write_text(json.dumps(review, indent=2) + '\n')
    return review


if __name__ == '__main__':
    print(json.dumps({'metrics': len(build()['synthetic_candidate_metrics'])}))
