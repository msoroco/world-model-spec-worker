"""Validate the canonical signal-onset controller parameter and stage chain."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    template = json.loads((HERE / 'proposals/template.json').read_text())
    binding = json.loads((HERE / 'proposals/bindings.json').read_text())
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    assert sum(x['name'] == 'signal_target_m' for x in template['parameter_refs']) == 1
    assert sum(x['name'] == 'signal_target_m' for x in binding['variable_parameters']) == 1
    for case in proposal['cases']:
        target = case['variable_assignments']['signal_target_m']
        assert target['kind'] == 'controller' and target['unit'] == 'm'
        expected = 25.0 if case['case_id'].endswith('__signal_advance_100_below_25') else (36.0 if case['case_id'].endswith('__signal_advance_100_above_36') else 30.48)
        assert target['value'] == expected
    print(validate(HERE, assignment, manifest))


if __name__ == '__main__':
    main()
