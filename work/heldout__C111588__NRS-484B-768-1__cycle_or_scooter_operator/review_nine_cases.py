"""Independent CPU-readiness review against frozen law and delivery contracts."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator'
assignment_path = REPO / 'inputs' / ASSIGNMENT / 'assignment.json'
assignment = json.loads(assignment_path.read_text())
plan = json.loads((ROOT / 'case-plan.json').read_text())
semantic = json.loads((ROOT / 'proposals/cases-stage-proposal.json').read_text())
by_semantic = {c['case_id']: c for c in semantic['cases'] if c['target_type'] != 'baseline'}
assert assignment['law']['text'].startswith('Except as otherwise provided in subsection 2')
assert len(plan['cases']) == len(by_semantic) == 9
assert len(plan['comparisons']) == 7
assert {c['case_id'] for c in plan['cases']} == set(by_semantic)
review = []
for case in plan['cases']:
    ident = case['case_id']
    slug = ident.rsplit('__', 1)[-1]
    source = ROOT / 'cases' / slug / 'construction.json'
    if not source.exists():
        source = ROOT / 'first-construction.json'
    construction = json.loads(source.read_text())
    manifest = ROOT / (slug.replace('_', '-') + '-manifest.json')
    if slug == 'bicycle_signal_once': manifest = ROOT / 'first-execution-manifest.json'
    elif slug == 'bicycle_no_signal': manifest = ROOT / 'no-signal-manifest.json'
    elif slug == 'bicycle_signal_continuous': manifest = ROOT / 'continuous-manifest.json'
    elif slug == 'electric_bicycle_signal_once': manifest = ROOT / 'electric-bicycle-manifest.json'
    elif slug == 'electric_scooter_signal_once': manifest = ROOT / 'electric-scooter-manifest.json'
    elif slug == 'both_hands_no_signal': manifest = ROOT / 'both-hands-manifest.json'
    elif slug == 'turn_lane_no_signal': manifest = ROOT / 'turn-lane-manifest.json'
    entry = json.loads(manifest.read_text())['cases'][0]
    expected = {row['name'] for row in by_semantic[ident]['recording_description']['channels']}
    actual = {row['name'] for row in construction['recording_description']['channels']}
    review.append({'case_id': ident, 'construction': str(source.relative_to(ROOT)),
                   'construction_sha256': sha256(source.read_bytes()).hexdigest(),
                   'exact_case_manifest': str(manifest.relative_to(ROOT)),
                   'fallback_count': len(entry.get('candidates', [])),
                   'physical_preparation_bound': 'physical_preparation' in entry,
                   'semantic_recording_channels': sorted(expected),
                   'exact_recording_channels': sorted(actual),
                   'semantic_channels_missing_from_exact': sorted(expected-actual),
                   'extra_exact_channels': sorted(actual-expected)})
assert all(row['fallback_count'] == 3 for row in review)
assert all(row['physical_preparation_bound'] for row in review)
branches = {'bicycle': {'bicycle_signal_once','bicycle_no_signal','bicycle_signal_continuous'},
            'electric_bicycle': {'electric_bicycle_signal_once'},
            'electric_scooter': {'electric_scooter_signal_once'},
            'designated_turn_lane_exception': {'turn_lane_no_signal'},
            'both_hands_exception': {'both_hands_no_signal'},
            'reasonable_safety': {'safety_wide','safety_narrow'}}
assert {slug for values in branches.values() for slug in values} == {c['case_id'].rsplit('__',1)[-1] for c in plan['cases']}
root_missing = [name for name in ('construction.json','config.json','runner.py','execution-manifest.json','proposals/semantic-index.json') if not (ROOT / name).is_file()]
report = {'format': 'worker-rider-nine-case-cpu-review', 'assignment_id': ASSIGNMENT,
          'frozen_assignment_sha256': sha256(assignment_path.read_bytes()).hexdigest(),
          'review_method': 'Re-read frozen law, each of nine semantic/exact descriptions, seven comparison pairs, and current exact manifests independently of builder scripts.',
          'law_branches': {name: sorted(values) for name, values in branches.items()},
          'cases': review, 'root_delivery_artifacts_missing': root_missing,
          'semantic_exact_recording_mismatch_count': sum(bool(row['semantic_channels_missing_from_exact'] or row['extra_exact_channels']) for row in review),
          'cpu_gaps': ['Canonical semantic recording plans demand six measured channels per exact case, but exact constructions currently capture only their case-specific subset; the common rider heading, participant clearance, time-to-conflict, hand-contact and stability channels need original acquisition/finalization and rerun proofs in the cases that still lack them.',
                       'Safety wide/narrow now acquire moving-participant positions and Native body half-width readback; their diagnostic finite closing-rate time-to-conflict is measured. The crossing mechanism and body geometry still require actual Native physical review.',
                       'Consolidated execution manifest, semantic index and nine positive/negative delivery-acceptance audit bindings validate. Semantic delivery validation still rejects nine canonical/exact recording-description mismatches.'],
          'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
          'ready_recommended': False}
(ROOT / 'nine-case-cpu-review.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'cases_reviewed': len(review), 'fallbacks_each': 3,
                  'semantic_exact_mismatches': report['semantic_exact_recording_mismatch_count'],
                  'root_artifacts_missing': root_missing, 'ready_recommended': False}))
