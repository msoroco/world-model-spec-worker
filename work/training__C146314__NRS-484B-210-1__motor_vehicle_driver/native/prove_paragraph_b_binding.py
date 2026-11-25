"""Recheck whether frozen scope can bind paragraph (b)."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT = 'training__C146314__NRS-484B-210-1__motor_vehicle_driver'
OUT = Path(__file__).with_name('paragraph-b-binding-proof.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen_path = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
    catalog_path = ROOT / 'inputs' / 'coverage' / 'candidate-cells.json'
    frozen = json.loads(frozen_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    cell = frozen['cell'] if 'cell' in frozen else frozen.get('frozen_cell')
    assert cell is not None
    assert cell['layout'] == 'one_way_multilane'
    assert cell['maneuver'] == 'overtake_right'
    assert cell['control'] == 'other_vehicle'
    candidates = [item for item in catalog['cells']
                  if item['maneuver'] == 'overtake_right'
                  and item['control'] == 'other_vehicle']
    eligible = [item for item in candidates
                if 'motor_vehicle_driver' in item.get('candidate_ego_parties', [])]
    close = [item for item in candidates
             if item['cell_id'] in ('C322959', 'C330169')]
    assert not eligible
    assert all(not item['candidate_ego_parties'] and not item['allocated_sets']
               for item in close)
    proof = {
        'format': 'c146314-paragraph-b-binding-proof-v1',
        'assignment_id': ASSIGNMENT,
        'frozen_assignment': str(frozen_path.relative_to(ROOT)),
        'frozen_assignment_sha256': sha(frozen_path),
        'candidate_catalog': str(catalog_path.relative_to(ROOT)),
        'candidate_catalog_sha256': sha(catalog_path),
        'source_law_sha256': frozen['local_snapshot']['law_sha256'],
        'paragraph_b_requires': 'Two or more lines of moving vehicles in each direction on unobstructed pavement free of parked vehicles',
        'frozen_layout': cell['layout'],
        'matching_maneuver_control_candidate_count': len(candidates),
        'actor_eligible_candidate_count': len(eligible),
        'near_two_way_candidates': [
            {'cell_id': item['cell_id'], 'layout': item['layout'],
             'candidate_ego_parties': item['candidate_ego_parties'],
             'allocated_sets': item['allocated_sets']}
            for item in close],
        'selected_binding': None,
        'status': 'unbound_source_constraint',
        'physical_or_legal_acceptance': False,
    }
    OUT.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print('PASS frozen one-way scope and candidate-catalog binding audit; paragraph (b) unbound')


if __name__ == '__main__':
    main()
