"""Bind every frozen C405647 1(b) topic to exact CPU evidence and remaining sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-267-1b'


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
    source = read(source_path)['laws'][LAW]
    plan, manifest, comparison = read(plan_path), read(manifest_path), read(comparison_path)
    if source['law']['text'] != plan['source_law_text']:
        raise ValueError('Frozen statutory text differs from plan')
    topics = source['topics']
    expected = {f'text-{i}' for i in range(10)} | {'reviewed-scope-0'}
    if set(topics) != expected:
        raise ValueError('Frozen topic inventory differs')
    cases = {AID + '__reference', AID + '__contrast'}
    if {c['case_id'] for c in plan['cases']} != cases or {c['case_id'] for c in manifest['cases']} != cases:
        raise ValueError('Paired case coverage differs')
    if comparison['manifest_sha256'] != sha(manifest_path) or len(comparison['pairs']) != 4:
        raise ValueError('Controlled comparison binding differs')
    if len(comparison['negative_mutations']) != 16:
        raise ValueError('Controlled source negatives incomplete')
    dispositions = {d['requirement']: d for d in plan['requirement_dispositions']}
    if set(dispositions) != expected:
        raise ValueError('Statutory disposition coverage differs')
    evidence = {
        'text-0': ('approach_catchup_frame; authority/lamp/officer source packet',
                   'original emergency or regulatory authority, qualifying flashing lamps and officer direction'),
        'text-1': ('first_edge_target_frame, stop_heading_deg, stop_center_xy_m and intersection geometry',
                   'original immediacy, parallel position and closest feasible right edge'),
        'text-2': ('stop_outer_body_y_m and signed shoulder source packet',
                   'original paved-shoulder geometry and lawfully placed sign'),
        'text-3': ('exclusion category source packet', 'original applicable exclusion category'),
        'text-4': ('authorized emergency identity', 'original authorized emergency identity'),
        'text-5': ('emergency vehicle permit', 'original permit evidence'),
        'text-6': ('traffic incident management identity', 'original traffic incident management identity'),
        'text-7': ('tow-car identity', 'original tow-car identity'),
        'text-8': ('coroner vehicle identity', 'original coroner identity'),
        'text-9': ('public transit bus and signed shoulder use',
                   'original bus identity, shoulder use and lawful sign'),
        'reviewed-scope-0': ('paired edge/catch-up/stop saved geometry',
                             'original activation, geometry and legal review'),
    }
    coverage = [{'topic_id': topic, 'text_sha256': hashlib.sha256(
                    topics[topic]['text'].encode()).hexdigest(),
                 'plan_disposition': dispositions[topic]['status'],
                 'synthetic_observable': evidence[topic][0],
                 'original_evidence_pending': evidence[topic][1],
                 'runnable': False}
                for topic in sorted(topics)]
    metrics = []
    for pair in comparison['pairs']:
        for case in ('reference', 'contrast'):
            value = pair['measured'][case]
            analysis_path = HERE / 'draft-candidates' / case / pair['candidate'] / 'finalization-analysis.json'
            analysis = read(analysis_path)
            geometry = analysis['measurements']['right_edge_geometry']['value']
            if (geometry['first_edge_target_frame'] != value['edge_frame'] or
                    geometry['approach_catchup_frame'] != value['catchup_frame'] or
                    geometry['vehicle_authority_or_lamps_qualified'] is not False or
                    geometry['legal_immediacy_or_edge_verdict'] is not None):
                raise ValueError('Candidate saved statutory measurement differs')
            metrics.append({'case_id': AID + '__' + case, 'candidate_id': pair['candidate'],
                            'edge_frame': value['edge_frame'],
                            'catchup_frame': value['catchup_frame'],
                            'stop_frame': value['stop_frame'],
                            'analysis_sha256': sha(analysis_path),
                            'original_qualification': False})
    review = {'format': 'c405647-1b-source-to-physical-branch-review-v1',
              'assignment_id': AID, 'law_id': LAW,
              'source_hashes': {'assignment.json': sha(assignment_path),
                                'branch-sources.json': sha(source_path),
                                'case-plan.json': sha(plan_path),
                                'draft-execution-manifest.json': sha(manifest_path),
                                'synthetic-controlled-comparison.json': sha(comparison_path)},
              'comparison_id': plan['comparisons'][0]['comparison_id'],
              'case_ids': sorted(cases), 'topics': coverage,
              'synthetic_candidate_metrics': metrics, 'negative_count': 16,
              'status': 'cpu_constructed_pending_original_and_legal_review',
              'runnable_branch_claimed': False, 'legal_verdict_claimed': False}
    (HERE / 'statutory-branch-review.json').write_text(json.dumps(review, indent=2) + '\n')
    return review


if __name__ == '__main__':
    result = build()
    print(f"{len(result['topics'])} topics; {len(result['synthetic_candidate_metrics'])} candidate rows")
