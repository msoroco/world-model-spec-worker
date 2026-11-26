"""Validate this assignment's semantic stages and saved measurement contracts."""

import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
sys.path.insert(1, str(ROOT / 'runtime' / 'python'))

from worker_exchange.measurement_contract import validate as validate_measurement
from worker_exchange.semantic_delivery import validate as validate_semantic


def main():
    assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    manifest = json.loads((FOLDER / 'draft-native-manifest.json').read_text())
    semantic = validate_semantic(FOLDER, assignment, manifest)
    analysis = (FOLDER / 'native' / 'saved_walking.py').read_text()
    requirements = {}
    for side in 'ab':
        case_id = FOLDER.name + '__selected_81846e7f__condition_' + side
        contract = json.loads((FOLDER / 'native' / ('measurement-' + side + '.json')).read_text())
        requirements[case_id] = len(validate_measurement(contract, plan['requirement_dispositions'], analysis, case_id))
    print(json.dumps({'semantic': semantic, 'measurement_requirements': requirements,
                      'source_scope': 'current pinned runtime; no physical or legal verdict'}))


if __name__ == '__main__':
    main()
