"""Build and validate the fixed Walk physical sweep before manifest promotion."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from batch_pipeline.sweeps import expand_sweeps


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment = read(REPO / 'inputs' / HERE.name / 'assignment.json')
    template = read(HERE / 'proposals/template.json')
    judgment = read(HERE / 'proposals/judgment_observables_right_of_way.json')
    binding = read(HERE / 'proposals/bindings.json')
    cases = read(HERE / 'proposals/cases.json')
    phrase = judgment['phrase']; note = judgment['note']
    dimension = {'name': 'crosswalk_hold_margin_m', 'unit': 'm',
                 'description': 'First requested bus hold distance from its measured front body edge to the authored marked crosswalk; physical coverage only.'}
    judgment['observable_requirements']['sweep_dimensions'] = [dimension]
    stages.validate('judgment_observables', judgment, {
        'request': {'template_id': template['template_id'], 'phrase': phrase, 'note': note},
        'dependencies': []})
    augmented = deepcopy(template)
    augmented['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
    reference = next(c for c in cases['cases'] if c['case_id'].endswith('__reference'))
    recording = deepcopy(reference['recording_description'])
    recording['channels'].append({
        'name': 'crosswalk_hold_margin_m', 'unit': 'm', 'sampling_rate_hz': 20,
        'method': 'Original Native four-corner bus front and controller hold request, joined to marked crosswalk y; retain full 480-row source',
        'time_window': '24 s / 480-frame attempt',
        'reference_frame': 'surveyed Native map crossing y=-11 m',
        'uncertainty': '50 ms sampling; original body/crosswalk geometry and actual motion still require review'})
    spec = {
        'sweep_id': HERE.name + '__right_of_way_physical_context',
        'target_law_id': assignment['law_id'],
        'judgment_refs': [{'phrase': phrase, 'note': note}],
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{
            'variable': 'crosswalk_hold_margin_m',
            'observable': 'crosswalk_hold_margin_m', 'unit': 'm',
            'min': 0.5, 'max': 2.0, 'spacing': 0.5,
            'measurement': {'method': 'first requested hold: marked crossing y minus observed bus front body y from full Native rows',
                            'time_window': '24 s / 480-frame attempt', 'statistic': 'first'},
            'range_rationale': 'Engineering margin samples within WalkYieldController validated (0,5] m domain; not a statutory cutoff.',
            'spacing_rationale': '0.5 m steps separate four fixed controller requests within the 3.5 m authored bus lane and near-crosswalk approach; no label adaptation.',
            'feasibility_evidence': 'native/controller.py WalkYieldController domain and native/geometry.py marked y=-11 m; update026 physical sweep CPU proof covers all 12 controller states.'}],
        'landmarks': [],
        'rationale': 'Fixed physical hold-request coverage for the Walk/right-of-way judgment; source review and legal judgment remain unresolved.',
        'variable_assignments': deepcopy(reference['variable_assignments']),
        'recording_description': recording,
    }
    # The canonical chain remains selected to two cases. This staged copy
    # expands four exact cases and can be promoted only with full construction
    # and manifest receipts for every new case.
    cases['sweep_specs'] = [spec]
    cases.pop('sweeps_expanded', None)
    expand_sweeps(cases, templates=[augmented], bindings=binding)
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    stages.validate('cases', cases, {
        'request': {'cell': assignment['cell'], 'actor': assignment['actor']},
        'dependencies': [binding], 'templates': [augmented],
        'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    sweep_cases = [c for c in cases['cases'] if c.get('sweep_id') == spec['sweep_id']]
    if len(sweep_cases) != 4 or [c['selection_rank'] for c in sweep_cases] != list(range(4)):
        raise ValueError('Fixed four-case sweep expansion differs')
    judgment_sha = write(HERE / 'proposals/sweep-observables-candidate.json', judgment)
    cases_sha = write(HERE / 'proposals/sweep-stage-candidate.json', cases)
    return {'stage_validated': True, 'sweep_cases': [c['case_id'] for c in sweep_cases],
            'selection_order': spec['selection_order'], 'judgment_sha256': judgment_sha,
            'cases_sha256': cases_sha, 'canonical_promoted': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
