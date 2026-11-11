"""Bind draft semantic artifacts to the frozen C111588 assignment."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = ROOT / 'inputs/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/assignment.json'


def check():
    frozen = json.loads(ASSIGNMENT.read_text())
    template = json.loads((FOLDER / 'template.json').read_text())
    bindings = json.loads((FOLDER / 'bindings.json').read_text())
    assert template['quote'] == frozen['law']['text']
    assert (template['law_id'], template['actor']) == (frozen['law_id'], frozen['actor'])
    assert (bindings['cell_id'], bindings['actor']) == (frozen['cell_id'], frozen['actor'])
    flagged = template['structure']['judgment_calls_needed']
    assert len(flagged) == 3
    for index, entry in enumerate(flagged, 1):
        assert entry['phrase'] in template['quote']
        separate = json.loads((FOLDER / f'judgment-{index}.json').read_text())
        assert (separate['phrase'], separate['note']) == (entry['phrase'], entry['note'])
        assert separate['template_id'] == template['template_id']
    assert {r['template_id'] for r in bindings['law_refs']} == {template['template_id']}
    return {'source_bound': True, 'judgment_contracts': len(flagged),
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
