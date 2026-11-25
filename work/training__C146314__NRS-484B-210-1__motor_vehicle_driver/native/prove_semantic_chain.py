"""Validate canonical semantic stages against exact selected draft constructions."""
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
GROUPS = ('selected-paragraph-d', 'exception-1', 'current-c1',
          'exception-4', 'subsection-4', 'numeric-boundary')


def main():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    assert '.runtime-work' in output_root.parts
    sys.path.insert(0, str(REPO / 'runtime'))
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from scenario_pipeline.worker_exchange.semantic_delivery import validate
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    cases = []
    for group in GROUPS:
        manifest = json.loads((ROOT / 'native' / group / 'manifest.json').read_text())
        for entry in manifest['cases']:
            selected = dict(entry)
            selected['construction'] = 'native/' + group + '/' + entry['construction']
            cases.append(selected)
    result = validate(ROOT, assignment, {'cases': cases})
    assert result['selected_cases'] == 13 and result['stage_count'] == 5
    checkpoint = {'format': 'c146314-semantic-cpu-v1',
                  'assignment_id': ROOT.name, 'canonical_validator': result,
                  'paragraph_b_selected': False,
                  'physical_or_legal_acceptance': False}
    (ROOT / 'proposals/semantic-cpu-checkpoint.json').write_text(
        json.dumps(checkpoint, indent=2) + '\n')
    print('PASS canonical semantic chain for 13 selected draft cases')


if __name__ == '__main__':
    main()
