"""Keep canonical case proposal identities aligned with exact selected bundles."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
MANIFEST = json.loads((ROOT / 'execution-manifest.json').read_text())


def main():
    selected = {item['case_id']: item for item in PLAN['cases']}
    cases = []
    for entry in MANIFEST['cases']:
        case_id = entry['case_id']
        planned = selected[case_id]
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = json.loads(next(file['content'] for file in construction['files']
                                 if file['path'] == 'config.json'))
        cases.append({
            'case_id': case_id,
            'target_law_id': PLAN['law_id'],
            'target_type': 'boundary_probe',
            'rationale': 'Source-reviewed school-crossing-zone speed and exception context: '
                         + planned['planned_context'],
            'cell_id': PLAN['cell_id'],
            'actor': PLAN['actor'],
            'variable_assignments': {
                'requested_bus_speed_mph': {'kind': 'controller',
                                            'value': config['target_mph'], 'unit': 'mph'},
                'reviewed_school_context': {'kind': 'controller',
                                            'value': config['planned_context'],
                                            'unit': 'category'},
                'observed_bus_speed_mph': {'kind': 'subject_behavior',
                                           'value': None, 'unit': 'mph'},
            },
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [
                'official school-crossing-zone designation and installed sign',
                'original bus, children and beacon/sign pixels',
                'school calendar, operation hours and timezone-aware civil time',
                'physical realization and legal applicability',
            ],
            'deliberate_differences': [planned['comparison_variable']],
            'probe': {'primary_variable': planned['comparison_variable'],
                      'comparison_or_standard': 'exact NRS 484B.363(2) 25 mph and four exceptions',
                      'target_value_or_branch': planned['planned_context']},
        })
    proposal = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
                'status': 'draft', 'sweep_specs': [], 'cases': cases}
    path = ROOT / 'proposals/cases.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    print(json.dumps({'proposed_selected_cases': len(cases)}, sort_keys=True))


if __name__ == '__main__':
    main()
