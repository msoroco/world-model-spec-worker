"""Independent frozen-topic and 480-row saved-evidence audit."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from prove_saved import packet


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


review = json.loads((HERE / 'statutory-branch-review.json').read_text())
source_path = ROOT / 'inputs/coverage/branch-sources.json'
assignment_path = ROOT / 'inputs' / HERE.name / 'assignment.json'
plan_path = HERE / 'case-plan.json'
manifest_path = HERE / 'draft-execution-manifest.json'
comparison_path = HERE / 'synthetic-controlled-comparison.json'
paths = {'assignment.json': assignment_path, 'branch-sources.json': source_path,
         'case-plan.json': plan_path, 'draft-execution-manifest.json': manifest_path,
         'synthetic-controlled-comparison.json': comparison_path}
assert review['source_hashes'] == {name: sha(path) for name, path in paths.items()}
source = json.loads(source_path.read_text())['laws']['NRS-484B-267-1b']
plan = json.loads(plan_path.read_text())
comparison = json.loads(comparison_path.read_text())
assert source['law']['text'] == plan['source_law_text']
assert review['law_id'] == 'NRS-484B-267-1b'
assert review['comparison_id'] == plan['comparisons'][0]['comparison_id']
assert set(review['case_ids']) == {HERE.name + '__reference', HERE.name + '__contrast'}
topics = {row['topic_id']: row for row in review['topics']}
assert set(topics) == set(source['topics']) == {f'text-{i}' for i in range(10)} | {'reviewed-scope-0'}
dispositions = {row['requirement']: row for row in plan['requirement_dispositions']}
for topic, text in source['topics'].items():
    row = topics[topic]
    assert row['text_sha256'] == hashlib.sha256(text['text'].encode()).hexdigest()
    assert row['plan_disposition'] == dispositions[topic]['status']
    assert row['synthetic_observable'] and row['original_evidence_pending']
    assert row['runnable'] is False
assert len(review['synthetic_candidate_metrics']) == 8
metric_index = {(row['case_id'].rsplit('__', 1)[-1], row['candidate_id']): row
                for row in review['synthetic_candidate_metrics']}
assert len(metric_index) == 8
for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
    pair = next(x for x in comparison['pairs'] if x['candidate'] == candidate)
    for case in ('reference', 'contrast'):
        rows = packet(case, candidate)[1]
        assert len(rows) == 480 and all(r['source_kind'] == 'synthetic_cpu' for r in rows)
        edge = next((i for i, r in enumerate(rows)
                     if r['subject']['center_xy_m'][1] <= -5.95 and
                     min(v[1] for v in r['subject']['body_xy_m']) >= -7), None)
        catchup = next((i for i, r in enumerate(rows)
                        if r['subject']['center_xy_m'][0] - r['approach']['center_xy_m'][0] <= 4.5), None)
        stop = next((i for i in range(471)
                     if max(r['subject']['speed_mps'] for r in rows[i:i+10]) <= .1), None)
        metric = metric_index[(case, candidate)]
        assert (metric['edge_frame'], metric['catchup_frame'], metric['stop_frame']) == (edge, catchup, stop)
        assert pair['measured'][case]['edge_frame'] == edge
        assert metric['analysis_sha256'] == sha(HERE / 'draft-candidates' / case / candidate /
                                                'finalization-analysis.json')
        assert metric['original_qualification'] is False
assert review['negative_count'] == len(comparison['negative_mutations']) == 16
assert review['status'] == 'cpu_constructed_pending_original_and_legal_review'
assert review['runnable_branch_claimed'] is False and review['legal_verdict_claimed'] is False
audit = {'format': 'c405647-1b-independent-statutory-review-audit-v1',
         'review_sha256': sha(HERE / 'statutory-branch-review.json'),
         'topic_count': 11, 'candidate_count': 8, 'saved_rows_recomputed': 3840,
         'negative_count': 16, 'runnable_branch_proven': False}
(HERE / 'statutory-branch-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print('independent statutory audit: 11 topics, 8 candidates, 3840 saved rows')
