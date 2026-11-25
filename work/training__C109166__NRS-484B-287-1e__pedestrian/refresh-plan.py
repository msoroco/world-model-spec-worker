"""Reconcile C109166 plan with exact CPU proofs and unresolved original sources."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    terms = {item['term']: item['note'] for item in
             json.loads((HERE.parents[1] / 'inputs' / HERE.name / 'assignment.json').read_text())
             ['source_observation_terms']}
    refs = {
        'ru.subject': ['pedestrian-original.jsonl'],
        'dev.pedestrian_signal': ['device-original.jsonl', 'diagonal-pixel-review.json'],
        'dev.regulatory_sign': ['authority/official_status.json'],
        'dev.governs': ['authority/movement_applicability.json'],
        'st.intersection': ['road-boundary-review.json'],
        'kin.path_length': ['pedestrian-original.jsonl'],
        'rel.occupies': ['pedestrian-original.jsonl', 'road-boundary-review.json'],
        'kin.time': ['video_frames.jsonl', 'device-original.jsonl']}
    plan['source_observation_mapping'] = {
        term: {'evidence': note + '; original source and independent review required at Native acceptance',
               'channels': [term], 'source_refs': refs[term]}
        for term, note in terms.items()}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'subject': 'complete pedestrian body and diagonal intersection',
             'interval': 'all 600 original frames', 'view': 'overview'},
            {'subject': 'pedestrian first road entry and full-body path',
             'interval': 'startup through final clearance', 'view': 'approach'},
            {'subject': 'official diagonal authorization and governing signage',
             'interval': 'startup through final observation', 'view': 'reference_corner'},
            {'subject': 'actual pedestrian head display pixels',
             'interval': 'before, at and after first entry', 'view': 'driver_reference'}]}
    for case in plan['cases']:
        case['kind'] = 'delivery_cpu_prepared_source_pending'
    plan['requirement_dispositions'][0]['evidence_or_gap'] = (
        'Exact primary/fallback constructions, 600-frame diagnostic sources, offline/public/saved positive and source-negative CPU proofs are bound. '
        'Original independently surveyed official diagonal authorization, Native movement and governing device pixels remain absent.')
    plan['requirement_dispositions'][1]['evidence_or_gap'] = (
        'Source-hashed NRS 484B.290 applicability measurement and independent review gate are implemented. '
        'Exact exception text and person-specific applicability remain absent from original source; the bracketed LVMC-11-30-140-B text is a separate mapped source.')
    plan['requirement_dispositions'][1]['status'] = 'selected_required'
    plan['requirement_dispositions'][1]['case_ids'] = [case['case_id'] for case in plan['cases']]
    plan['runtime_uncertainties'] = [
        'The requested Native head ID is not an independently surveyed official diagonal device.',
        'No original Native 600-frame capture, original displayed pixels or reviewed road boundary exists.',
        'No original person-specific evidence resolves NRS 484B.290 applicability.',
        'Synthetic compatibility and physical fixture outcomes prove software paths only.']
    plan['blockers'] = [
        'Independent original survey media tying official diagonal authorization and movement applicability to the requested Native head are absent.',
        'Original Native device pixels, full-body boundary review and person-specific exception evidence are absent.']
    path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'mapping_terms': len(terms), 'status': 'source_review_pending'}))


if __name__ == '__main__':
    main()
