"""Check every frozen turn cell and existing assignment for right/left eligibility."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAW = 'LVMC-11-40-080'
ACTOR = 'cycle_or_scooter_operator'


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    catalog_path = REPO / 'inputs/coverage/candidate-cells.json'
    batch_path = REPO / 'batch.json'
    assignment_path = REPO / 'inputs' / HERE.name / 'assignment.json'
    staged_path = HERE / 'staged-turn-cells/staging-execution-manifest.json'
    catalog = load(catalog_path)['cells']
    batch = load(batch_path)
    original = load(assignment_path)
    staged = load(staged_path)
    if (original['law_id'] != LAW or original['actor'] != ACTOR or
            original['cell_id'] != 'C104538' or
            original['cell']['maneuver'] != 'u_turn' or
            original['cell']['control'] != 'turn_prohibition_device'):
        raise ValueError('Original frozen scope differs')
    original_cell = next(row for row in catalog if row['cell_id'] == 'C104538')
    if (original_cell['maneuver'] != 'u_turn' or
            original_cell['control'] != 'turn_prohibition_device'):
        raise ValueError('Original catalog cell differs')

    existing = []
    for aid in batch['assignments']:
        path = REPO / 'inputs' / aid / 'assignment.json'
        if path.is_file():
            row = load(path)
            if row.get('law_id') == LAW:
                existing.append({'assignment_id': aid, 'cell_id': row['cell_id'],
                                 'maneuver': row['cell']['maneuver'],
                                 'actor': row['actor'], 'role': row['role']})
    if len(existing) != 1 or existing[0]['assignment_id'] != HERE.name:
        raise ValueError('Same-law frozen assignment inventory differs')

    staged_ids = {row['case_id'] for row in staged['cases']}
    alternatives = []
    for maneuver, staged_cell in (('left_turn', 'C102581'),
                                  ('right_turn', 'C103714')):
        rows = [row for row in catalog if row['maneuver'] == maneuver and
                row['control'] == 'turn_prohibition_device']
        matching_layout = [row for row in rows if row['layout'] == original['cell']['layout']]
        if len(matching_layout) != 1 or matching_layout[0]['cell_id'] != staged_cell:
            raise ValueError('Exact staged turn cell changed')
        prefix = f'training__{staged_cell}__{LAW}__{ACTOR}__'
        cases = sorted(cid for cid in staged_ids if cid.startswith(prefix))
        if len(cases) != 2:
            raise ValueError('Exact staged comparison changed')
        alternatives.append({
            'maneuver': maneuver, 'catalog_prohibition_cell_count': len(rows),
            'actor_eligible_cell_ids': [row['cell_id'] for row in rows if
                                        ACTOR in row['candidate_ego_parties']],
            'exact_layout_cell_id': staged_cell,
            'exact_layout_actor_eligible': ACTOR in matching_layout[0]['candidate_ego_parties'],
            'exact_layout_allocated_sets': matching_layout[0]['allocated_sets'],
            'staged_case_ids': cases,
        })
    report = {
        'format': 'c104538-all-turn-cell-eligibility-v1',
        'assignment_id': HERE.name, 'law_id': LAW, 'actor': ACTOR,
        'catalog_cell_count': len(catalog),
        'catalog_actor_eligible_count': sum(ACTOR in row['candidate_ego_parties']
                                            for row in catalog),
        'catalog_any_actor_eligible_count': sum(bool(row['candidate_ego_parties'])
                                                for row in catalog),
        'same_law_frozen_assignments': existing,
        'original_cell': {'cell_id': original_cell['cell_id'],
                          'maneuver': original_cell['maneuver'],
                          'control': original_cell['control'],
                          'layout': original_cell['layout']},
        'right_left_alternatives': alternatives,
        'source_sha256': {
            'catalog': sha(catalog_path), 'batch': sha(batch_path),
            'original_assignment': sha(assignment_path),
            'staged_manifest': sha(staged_path), 'audit': sha(Path(__file__)),
        },
        'conclusion': 'No frozen catalog cell is actor-eligible for a supplemental right/left binding. The only same-law frozen assignment is the U-turn cell. The staged right/left comparison pairs remain CPU source constructions, not selectable packages.',
        'physical_or_legal_acceptance_claimed': False,
    }
    target = HERE / 'all-turn-cell-eligibility.json'
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'report_sha256': sha(target),
                      'catalog_cell_count': len(catalog),
                      'actor_eligible_count': report['catalog_actor_eligible_count'],
                      'left_right_counts': [row['catalog_prohibition_cell_count']
                                            for row in alternatives]}, sort_keys=True))


if __name__ == '__main__':
    main()
