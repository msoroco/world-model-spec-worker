"""Independent exact-source and raw-observation audit of the pending C422978 branch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-38-030'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    review_path = HERE / 'statutory-branch-review.json'
    review = read(review_path)
    source = read(ROOT / 'inputs/coverage/branch-sources.json')['laws'][LAW]
    assignment = read(ROOT / 'inputs' / AID / 'assignment.json')
    plan = read(HERE / 'case-plan.json')
    manifest = read(HERE / 'draft-execution-manifest.json')
    assert review['format'] == 'c422978-source-to-physical-branch-review-v1'
    assert review['assignment_id'] == AID and review['law_id'] == LAW
    assert assignment['law_id'] == LAW and assignment['cell_id'] == 'C422978'
    assert source['law']['text'] == plan['source_law']['text'] == \
        'No motorcycle or motor scooter shall be ridden upon any sidewalk of the City.'
    assert review['topic_ids'] == sorted(source['topics']) == ['reviewed-scope-0', 'text-0']
    assert review['case_ids'] == [c['case_id'] for c in plan['cases']]
    assert review['comparison_ids'] == [c['comparison_id'] for c in plan['comparisons']]
    assert {c['case_id'] for c in manifest['cases']} == set(review['case_ids'])
    assert review['status'] == 'cpu_constructed_pending_original_and_legal_review'
    assert review['runnable_branch_claimed'] is False
    assert review['city_authority_claimed'] is False and review['legal_verdict_claimed'] is False
    assert {item['element'] for item in review['statutory_elements']} == {
        'motorcycle or motor scooter', 'ridden upon a sidewalk', 'of the City',
        'driveway crossing composition'}
    assert all(item['original_status'] == 'unverified' for item in review['statutory_elements'])
    expected_sources = {
        'assignment.json': ROOT / 'inputs' / AID / 'assignment.json',
        'branch-sources.json': ROOT / 'inputs/coverage/branch-sources.json',
        'case-plan.json': HERE / 'case-plan.json',
        'draft-execution-manifest.json': HERE / 'draft-execution-manifest.json',
        'synthetic-controlled-comparison.json': HERE / 'synthetic-controlled-comparison.json',
        'native/context-proof.json': HERE / 'native/context-proof.json'}
    assert review['source_hashes'] == {name: sha(path) for name, path in expected_sources.items()}
    metrics = review['synthetic_candidate_metrics']
    assert len(metrics) == 8
    assert {(m['case_id'], m['candidate_id']) for m in metrics} == {
        (AID + '__' + suffix, candidate)
        for suffix in ('witness_1', 'witness_2')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    comparison = read(HERE / 'synthetic-controlled-comparison.json')
    assert len(comparison['rows']) == 4
    assert review['synthetic_negative_count'] == sum(len(row['negatives'])
                                                       for row in comparison['rows']) == 16
    audited = []
    for metric in metrics:
        suffix = metric['case_id'].rsplit('__', 1)[-1]
        candidate = metric['candidate_id']
        folder = HERE / 'native/saved-fixtures' / suffix / candidate
        packet = [json.loads(line) for line in (folder / 'native-observed.jsonl').read_text().splitlines()]
        assert len(packet) == 480
        assert all(row['frame'] == index and row['source_kind'] == 'synthetic_cpu'
                   and row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
                   for index, row in enumerate(packet))
        full_body = 0
        overlap = 0
        intersects = 0
        for row in packet:
            ys = [point[1] for point in row['body_native_xy_m']]
            if row['speed_mps'] > .1:
                full_body += min(ys) >= 3.5 and max(ys) <= 5.5
                overlap += min(ys) < 5.5 and max(ys) > 3.5
                intersects += min(ys) <= 5.5 and max(ys) >= 3.5
        assert metric['moving_sidewalk_overlap_frames'] == overlap
        assert metric['full_body_inside_sidewalk_frames'] == full_body
        assert metric['moving_sidewalk_intersection_frames'] == intersects
        assert metric['candidate_city_sidewalk_non_driveway_frames'] == intersects
        context_dir = HERE / 'native/context-fixtures' / suffix / candidate
        context = read(context_dir / 'city-context.json')
        measured = read(context_dir / 'context-measurement.json')
        assert context['authority_kind'] == 'synthetic_cpu'
        assert context['city_authority_reviewed'] is False
        assert context['driveway_crossing_polygons'] == []
        assert measured['city_authority_reviewed'] is False
        assert measured['driveway_rule_composition_reviewed'] is False
        assert measured['legal_verdict'] is None
        assert measured['moving_sidewalk_intersection_frames'] == intersects
        assert metric['context_measurement_sha256'] == sha(context_dir / 'context-measurement.json')
        audited.append({'case_id': metric['case_id'], 'candidate_id': candidate,
                        'moving_overlap_frames': overlap,
                        'full_body_inside_frames': full_body,
                        'sidewalk_intersection_frames': intersects})
    result = {'format': 'c422978-independent-statutory-review-audit-v1',
              'review_sha256': sha(review_path), 'audited': audited,
              'source_topics_verified': 2, 'synthetic_negative_count': 16,
              'runnable_or_legal_claimed': False}
    (HERE / 'statutory-branch-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited'])}))
