"""Validate the canonical exact-case proposal against pinned semantic rules."""
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main():
    output = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    assert '.runtime-work' in output.parts
    from batch_pipeline import stages
    proposal = HERE/'proposals'
    read = lambda name: json.loads((proposal/name).read_text())
    template = read('template.json')
    template['structure']['judgment_calls_needed'][0]['observable_requirements'] = (
        read('judgment-visibility.json')['observable_requirements'])
    inputs = {'request': {'cell': {'cell_id': 'C179824'},
                          'actor': 'motor_vehicle_driver'},
              'dependencies': [read('bindings.json')], 'templates': [template]}
    cases = read('cases.json')
    stages.validate('cases', cases, inputs)
    print(json.dumps({'passed': True, 'stage': 'cases',
                      'case_count': len(cases['cases']),
                      'diagnostic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
