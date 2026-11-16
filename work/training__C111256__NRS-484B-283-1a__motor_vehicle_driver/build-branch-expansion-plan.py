"""Map seven statutory branches to selected cases and measured CPU probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case(name):
    return HERE.name + '__' + name


selected = json.loads((HERE / 'execution-manifest.json').read_text())
opposite = json.loads((HERE / 'opposite-half-proofs/manifest.json').read_text())
additional = json.loads((HERE / 'additional-branch-proofs/manifest.json').read_text())
review = json.loads((HERE / 'statutory-review.json').read_text())
assert len(review['branches']) == 7
assert len(selected['cases']) == 4 and len(opposite['cases']) == 2 and len(additional['cases']) == 8
mapping = {
    'cited_287_crossing_restrictions': ['crosswalk_inside', 'crosswalk_outside'],
    'cited_290_blind_white_cane': ['exception_1_1', 'exception_1_2',
                                   'service_animal_absent', 'service_animal_present'],
    'cited_350_school_pedestrian_lane': ['guard_direction', 'guard_absent'],
    'uncontrolled_marked_crosswalk_ego_half_yield': ['witness_1', 'witness_2'],
    'opposite_half_near_danger_alternative': ['opposite_half_near', 'opposite_half_farther'],
    'directional_half_definition': ['direction_two_way', 'direction_one_way'],
    'ego_half_crosswalk_witness': ['witness_1', 'witness_2'],
}
selected_ids = {x['case_id'] for x in selected['cases']}
probe_ids = {x['case_id'] for x in opposite['cases']} | {x['case_id'] for x in additional['cases']}
branches = []
for item in review['branches']:
    names = mapping[item['id']]
    ids = [case(name) for name in names]
    assert all(cid in selected_ids | probe_ids for cid in ids)
    branches.append({'branch_id': item['id'], 'source_topics': item['source_topics'],
                     'case_ids': ids,
                     'selected_current_runtime_case_ids': [cid for cid in ids if cid in selected_ids],
                     'source_shaped_cpu_probe_case_ids': [cid for cid in ids if cid in probe_ids],
                     'legal_verdict': None, 'original_native_observed': False,
                     'status': 'partial',
                     'remaining_cpu_work': ([
                         'Implement Native geometry/actor construction for each probe case',
                         'Add each case to case-plan, semantic cases, and selected execution manifest',
                         'Supply four-camera fixture recipes, measurement contracts and exact public positive/negative/saved proofs for primary and three fallbacks',
                         'Extend independent delivery and comparison audits for exact originals']
                         if any(cid in probe_ids for cid in ids) else []),
                     'remaining_physical_review': (
                         'Original school crossing guard direction, actor role, and highway-clear observation remain unverified; no 50-foot stop is asserted'
                         if item['id'] == 'cited_350_school_pedestrian_lane'
                         else item['remaining_exact_evidence'])})
source_correction = {'format': 'c111256-statute-source-correction-v1',
    'official_source': 'https://www.leg.state.nv.us/nrs/nrs-484b.html',
    'source_review_date': '2026-11-15',
    'correction': 'NRS 484B.350 requires a driver to stop in obedience to a school crossing guard and not proceed until the highway is clear of all persons. The earlier statutory-review.json phrase “50-foot stop” has no basis in this cited section and must be removed when that source-hashed review is regenerated.',
    'nrs_484b_287_observation': 'Outside-marked-crosswalk and pedestrian tunnel/overhead crossing alternatives, plus controlled-intersection and diagonal-crossing restrictions, need separate applicability review; the current probe tests only inside versus outside marked crosswalk.',
    'nrs_484b_290_observation': 'Blind pedestrian eligibility may use a service animal or qualifying white cane or stick; declaration and source-shaped geometry do not prove eligibility.',
    'scope': 'Source review correction and CPU case planning only; no legal adjudication'}
(HERE / 'statutory-source-correction.json').write_text(json.dumps(source_correction, indent=2) + '\n')
result = {'format': 'c111256-seven-branch-cpu-expansion-plan-v1',
          'assignment_id': HERE.name,
          'frozen_input_sha256': sha(ROOT / 'inputs' / HERE.name / 'assignment.json'),
          'current_selected_manifest_sha256': sha(HERE / 'execution-manifest.json'),
          'opposite_half_probe_sha256': sha(HERE / 'opposite-half-proofs/manifest.json'),
          'additional_probe_sha256': sha(HERE / 'additional-branch-proofs/manifest.json'),
          'source_correction_sha256': sha(HERE / 'statutory-source-correction.json'),
          'branch_count': 7, 'additional_probe_case_count': 10,
          'additional_probe_candidate_count': 40,
          'additional_selected_delivery_case_count': 0,
          'branches': branches,
          'remaining_global_cpu_work': [
              'Extend NRS 484B.287 review beyond inside/outside crosswalk to its tunnel, signalized-between-intersections and diagonal restrictions where compatible with frozen cell',
              'Implement original-source school crossing guard role/command and highway-clear measurement; no invented 50-foot stop',
              'Implement physical white-cane/service-animal construction and eligibility review without inferring it from declarations',
              'Measure opposite-half body proximity and time without inventing a legal danger threshold',
              'Rebuild canonical semantic sweep, selected manifest and all hash-bound public proofs after expansion'],
          'legal_verdict': None, 'original_native_observed': False,
          'status': 'partial'}
(HERE / 'branch-expansion-plan.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'branches': 7, 'additional_probe_cases': 10,
                  'additional_probe_candidates': 40, 'additional_selected_delivery_cases': 0}))
