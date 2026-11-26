"""Inventory frozen actor/cell bindings for the subsection-3 cycle exceptions."""
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TARGET = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    batch_path = REPO / 'batch.json'
    cells_path = REPO / 'inputs/coverage/candidate-cells.json'
    batch = json.loads(batch_path.read_text())
    cells = json.loads(cells_path.read_text())['cells']
    cycle = []
    for aid in sorted(batch['assignments']):
        if not aid.endswith('__cycle_or_scooter_operator'):
            continue
        path = REPO / 'inputs' / aid / 'assignment.json'
        source = json.loads(path.read_text())
        cell = source['cell']
        cycle.append({'assignment_id': aid, 'cell_id': cell['cell_id'],
                      'layout': cell['layout'], 'maneuver': cell['maneuver'],
                      'control': cell['control'], 'input_sha256': sha(path)})
    exact = [x for x in cycle if x['layout'] == 'road' and
             x['maneuver'] in ('park', 'stop_stand') and x['control'] == 'sidewalk']
    candidates = [x['cell_id'] for x in cells if x['layout'] == 'road' and
                  x['maneuver'] in ('park', 'stop_stand') and x['control'] == 'sidewalk']
    return {'format': 'c229977-cycle-actor-binding-audit-v1',
            'target_assignment_id': TARGET,
            'batch_sha256': sha(batch_path), 'candidate_cells_sha256': sha(cells_path),
            'cycle_actor_assignments_examined': len(cycle),
            'exact_cycle_sidewalk_assignments': exact,
            'exact_candidate_sidewalk_cells': candidates,
            'nearest_cycle_park_cells': [x for x in cycle if x['layout'] == 'road' and
                                         x['maneuver'] == 'park'],
            'new_binding_authorized': False,
            'subsection_3_accepted': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
