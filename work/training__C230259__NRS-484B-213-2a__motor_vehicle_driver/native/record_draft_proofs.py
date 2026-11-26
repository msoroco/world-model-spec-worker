"""Record exact unselected offline receipts and all statutory alternatives."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c230259-nrs213'
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest = ROOT / 'draft-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    assert [e['case_id'].split('__')[-1] for e in entries] == list(SUFFIXES)
    receipts = []
    for entry, suffix in zip(entries, SUFFIXES):
        log = SCRATCH / ('offline-v3-' + suffix) / 'offline.log'
        if 'OK' not in log.read_text() or 'Ran 4 tests' not in log.read_text():
            raise ValueError('missing passing exact offline tests: ' + suffix)
        source = ROOT / entry['construction']
        if sha(source) != entry['construction_sha256']:
            raise ValueError('construction hash mismatch: ' + suffix)
        retained = ROOT / 'native' / ('draft-' + suffix + '-offline.log')
        retained.write_text(log.read_text().rstrip() + '\n')
        receipts.append({'case_id': entry['case_id'], 'construction_sha256': sha(source),
                         'offline_exit_code': 0, 'offline_log': str(retained.relative_to(ROOT)),
                         'offline_log_sha256': sha(retained), 'tests': 4})
    proof = {'format': 'worker-unselected-offline-proof-v2', 'assignment_id': ROOT.name,
             'manifest_sha256': sha(manifest), 'cases': receipts, 'selected_delivery': False,
             'native_executed': False, 'original_physical_observed': False}
    write(ROOT / 'native/draft-proof.json', proof)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    case_ids = [ROOT.name + '__' + s for s in SUFFIXES]
    plan['requirement_dispositions'][0]['case_ids'] = case_ids
    plan['requirement_dispositions'][0]['evidence_or_gap'] = 'Six exact unselected offline constructions cover crest, curve, and one-way exception requests. Selected Native acquisition, source-bound compatibility, independent audits, and original physical/legal review remain pending.'
    kinds = ('crest right-side reference', 'crest left-side contrast', 'curve right-side reference',
             'curve left-side contrast', 'one-way crest exception context', 'one-way curve exception context')
    plan['cases'] = [{'case_id': ident, 'target_law_id': 'NRS-484B-213-2a',
                      'kind': 'planned_only', 'target_type': 'applicability_negative' if s.startswith('one_way') else 'physical_contrast_request',
                      'physical_target': kind, 'comparison_variable': 'road_directionality' if s.startswith('one_way') else 'left_of_center_during_obstructed_feature',
                      'construction': 'draft-cases/' + s + '/primary/construction.json'}
                     for ident, s, kind in zip(case_ids, SUFFIXES, kinds)]
    fixed = ['frozen cell, actor, law, 600 frames at 20 Hz, four-camera policy, controller schedule, weather, participant identity policy']
    plan['comparisons'] = [
        {'comparison_id': ROOT.name + '__crest_left_side', 'case_ids': case_ids[:2],
         'fixed_conditions': fixed + ['two-way crest road geometry and opposing participant'],
         'deliberate_differences': ['requested left-of-center occupancy during crest approach']},
        {'comparison_id': ROOT.name + '__curve_left_side', 'case_ids': case_ids[2:4],
         'fixed_conditions': fixed + ['two-way curve road geometry and opposing participant'],
         'deliberate_differences': ['requested left-of-center occupancy during curve']},
        {'comparison_id': ROOT.name + '__crest_one_way_exception', 'case_ids': [case_ids[1], case_ids[4]],
         'fixed_conditions': fixed + ['crest profile and leftward trajectory request'],
         'deliberate_differences': ['two-way versus one-way road authority and lane geometry', 'opposing versus same-direction participant']},
        {'comparison_id': ROOT.name + '__curve_one_way_exception', 'case_ids': [case_ids[3], case_ids[5]],
         'fixed_conditions': fixed + ['curve profile and leftward trajectory request'],
         'deliberate_differences': ['two-way versus one-way road authority and lane geometry', 'opposing versus same-direction participant']},
    ]
    plan['runtime_uncertainties'] = ['No original Native crest/curve sightline, one-way authority, exact footprint or four-camera pixels observed.',
                                     'Unselected drafts do not prove source-bound selected capture, finalization, compatibility, recorded-only processing, semantic proposals, physical completion or independent audits.',
                                     'Hazard-creating distance remains an unquantified legal judgment.']
    write(plan_path, plan)
    print(json.dumps({'cases': len(receipts), 'comparisons': len(plan['comparisons']),
                      'draft_proof_sha256': sha(ROOT / 'native/draft-proof.json'),
                      'case_plan_sha256': sha(plan_path)}))


if __name__ == '__main__':
    main()
