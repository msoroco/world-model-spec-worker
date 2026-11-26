"""Bind the selected below/at/above plan without claiming original motion."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT/'case-plan.json'
    plan = json.loads(path.read_text())
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    selected = {entry['case_id']: entry for entry in manifest['cases']}
    for case in plan['cases']:
        entry = selected[case['case_id']]
        case['kind'] = 'delivery'
        case['construction'] = entry['construction']
        case['gap_ids'] = ['current_original_speed_source_review']
    plan['requirement_dispositions'][0]['evidence_or_gap'] = (
        'Selected 75, 80 and 85 mph left-turn cases and an 85 mph spawn fallback have '
        'current-runtime offline, source-bound positive/missing-source negative compatibility, '
        'recorded-only saved and physical/lifecycle CPU fixture proofs. Original Native velocity, '
        'camera pixels, maneuver completion and exact boundary interpretation await local review.')
    plan['evidence_review'].update({
        'method': 'Reviewed frozen accepted membership and C329610 review-context comparison rows; no original media, trace or exact source-hashed equivalence receipt is exported.',
        'reviewer': 'worker CPU source review', 'facts': [],
        'gaps': [{'id':'current_original_speed_source_review',
                  'requirement':'NRS-484B-600-1e absolute 80 mph original speed',
                  'source':'NRS 484B.600(1)(e)',
                  'why_existing_insufficient':'Three accepted IDs are membership-only here; their original Native velocity, left-turn source join, media and exact equivalence receipts are absent.'}]})
    plan['runtime_uncertainties'] = [
        'Original Native velocity may differ from 75/80/85 mph controller requests; the 85 mph fallback triggers only on measured failure.',
        'Real same-cell left-turn motion, source-camera visibility and original pixel review remain unverified.',
        'The exact 80 mph legal boundary cannot be resolved from floating-point synthetic diagnostic precision.']
    plan['construction_checkpoint'] = {
        'manifest':'execution-manifest.json', 'manifest_sha256':sha(ROOT/'execution-manifest.json'),
        'comparison_diagnostic':'selected-comparison-diagnostic.json',
        'comparison_diagnostic_sha256':sha(ROOT/'selected-comparison-diagnostic.json'),
        'selected':True, 'original_native_observed':False,
        'boundary_targets_mph':[75,80,85]}
    path.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main()
