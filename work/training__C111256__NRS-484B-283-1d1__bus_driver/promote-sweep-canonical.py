"""Promote the reviewed four-case Walk margin sweep into canonical work files."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.delivery_handoff import validate_case as validate_delivery
from worker_exchange.measurement_contract import validate as validate_measurements
from worker_exchange.physical_preparation import validate as validate_physical


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    before = read(HERE / 'execution-manifest.json')
    sweep = read(HERE / 'sweep-delivery-bound-candidate.json')
    proposal = read(HERE / 'proposals/sweep-stage-candidate.json')
    plan = read(HERE / 'case-plan-sweep-candidate.json')
    judgment = read(HERE / 'proposals/sweep-observables-candidate.json')
    template = read(HERE / 'proposals/template.json')
    binding = read(HERE / 'proposals/bindings.json')
    assignment = read(REPO / 'inputs' / HERE.name / 'assignment.json')
    if (len(before['cases']) != 2 or len(sweep['cases']) != 4 or
            len(plan['cases']) != 6 or len(proposal['cases']) != 7 or
            before['assignment_id'] != sweep['assignment_id'] == plan['assignment_id'] == HERE.name or
            before['runtime_manifest_sha256'] != sweep['runtime_manifest_sha256']):
        raise ValueError('Current two-case selection or four-case sweep differs')
    old_ids = {row['case_id'] for row in before['cases']}
    sweep_ids = {row['case_id'] for row in sweep['cases']}
    if (len(old_ids) != 2 or len(sweep_ids) != 4 or old_ids & sweep_ids or
            {row['case_id'] for row in plan['cases']} != old_ids | sweep_ids or
            {row['case_id'] for row in proposal['cases'] if row['target_type'] != 'baseline'}
            != old_ids | sweep_ids):
        raise ValueError('Selected case IDs differ from the reviewed stage and plan')
    template = copy.deepcopy(template)
    template['structure']['judgment_calls_needed'][0]['observable_requirements'] = \
        judgment['observable_requirements']
    stages.validate('judgment_observables', judgment, {
        'request': {'template_id': template['template_id'],
                    'phrase': judgment['phrase'], 'note': judgment['note']},
        'dependencies': []})
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    stages.validate('cases', proposal, {
        'request': {'cell': assignment['cell'], 'actor': assignment['actor']},
        'dependencies': [binding], 'templates': [template],
        'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    for entry in sweep['cases']:
        validate_candidates(HERE, entry, plan['law_id'], plan['cell_id'],
                            required=True, require_alternate=True, candidate_count=4)
        validate_physical(REPO, HERE, entry)
        validate_delivery(HERE, entry, {'full-train'})
        construction = read(HERE / entry['construction'])
        analysis = next(file['content'] for file in construction['files']
                        if file['path'] == entry['measurement_procedure']['entrypoint'])
        validate_measurements(read(HERE / entry['measurement_contract']),
                              plan['requirement_dispositions'], analysis, entry['case_id'])
    backup = HERE / 'update036-prepromotion'
    if backup.exists():
        raise ValueError('Preserve prior promotion checkpoint; choose a fresh promotion tag')
    backup.mkdir()
    targets = {'case-plan.json': 'case-plan.json',
               'execution-manifest.json': 'execution-manifest.json',
               'proposals/cases.json': 'proposals-cases.json',
               'proposals/template.json': 'proposals-template.json',
               'proposals/judgment_observables_right_of_way.json': 'proposals-judgment.json'}
    previous = {}
    for relative, name in targets.items():
        source = HERE / relative
        shutil.copy2(source, backup / name)
        previous[relative] = sha(source)
    merged = copy.deepcopy(before)
    merged['cases'].extend(copy.deepcopy(sweep['cases']))
    merged['status'] = 'partial_six_selected_final_manifest_reproof_pending'
    review = merged['selection_review']
    review['case_plan_sha256'] = None
    review['draft_proposal_sha256'] = None
    review['scope'] = ('Six exact CPU delivery cases selected: reference/contrast and four '
                       'physical Walk hold-margin probes; final-manifest proof refresh '
                       'and original source review remain pending')
    write(HERE / 'proposals/judgment_observables_right_of_way.json', judgment)
    write(HERE / 'proposals/cases.json', proposal)
    write(HERE / 'case-plan.json', plan)
    review['case_plan_sha256'] = sha(HERE / 'case-plan.json')
    review['draft_proposal_sha256'] = sha(HERE / 'proposals/cases.json')
    write(HERE / 'execution-manifest.json', merged)
    report = {'format': 'c111256-canonical-sweep-promotion-v1',
              'old_case_ids': sorted(old_ids), 'added_case_ids': sorted(sweep_ids),
              'backup_sha256': {name: sha(backup / name) for name in targets.values()},
              'old_sha256': previous, 'new_sha256': {name: sha(HERE / name) for name in targets},
              'selected_cases': 6, 'candidate_bundles': 24,
              'final_manifest_proofs_refreshed': False,
              'original_recordings_accepted': 0}
    write(HERE / 'update036-canonical-promotion.json', report)
    print(json.dumps({'selected_cases': 6, 'candidate_bundles': 24,
                      'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'final_manifest_proofs_refreshed': False,
                      'original_recordings_accepted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
