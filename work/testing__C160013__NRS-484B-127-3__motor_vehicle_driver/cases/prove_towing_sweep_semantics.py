"""Validate a three-case semantic draft without changing selected delivery."""
import hashlib
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-towing-sweep-semantic-stage'
ROOT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not ROOT.is_relative_to((REPO / '.runtime-work').resolve()):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate
from batch_pipeline.sweeps import expand_sweeps


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / 'cases').mkdir(parents=True)
    shutil.copytree(PACKAGE / 'proposals', STAGE / 'proposals')
    assignment = json.loads((REPO / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
    manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        source = PACKAGE / entry['construction']
        target = STAGE / entry['construction']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    towing = json.loads((PACKAGE / 'towing-diagnostic-manifest.json').read_text())['cases'][0]
    tow_entry = {'case_id': towing['case_id'],
                 'construction': towing['construction'], 'kind': 'delivery'}
    manifest['cases'].append(tow_entry)
    shutil.copyfile(PACKAGE / towing['construction'], STAGE / towing['construction'])
    bindings_path = STAGE / 'proposals/bindings.json'
    bindings = json.loads(bindings_path.read_text())
    bindings['variable_parameters'].append({
        'name': 'drawing_drawn_combination', 'kind': 'world_setup',
        'range_or_domain': 'original source-backed drawing and drawn actor relationship',
        'used_by_laws': ['NRS-484B-127-3']})
    bindings['variable_parameters'].append({
        'name': 'inter_body_opening', 'kind': 'subject_behavior',
        'range_or_domain': 'measured original complete-body opening',
        'used_by_laws': ['NRS-484B-127-3']})
    bindings_path.write_text(json.dumps(bindings, indent=2) + '\n')
    cases_path = STAGE / 'proposals/cases.json'
    cases = json.loads(cases_path.read_text())
    for case in cases['cases']:
        case['variable_assignments']['drawing_drawn_combination'] = {
            'kind': 'world_setup', 'value': False}
        case['variable_assignments']['inter_body_opening'] = {
            'kind': 'subject_behavior', 'value': None}
    wide = next(item for item in cases['cases'] if item['case_id'].endswith('__entrant_can_occupy_gap'))
    tow = deepcopy(wide)
    tow['case_id'] = towing['case_id']
    tow['rationale'] = 'Full drawing-and-drawn body gap and entrant occupancy; statutory danger unresolved.'
    tow['paired_probe_id'] = 'towing_combination_contrast'
    tow['variable_assignments']['drawing_drawn_combination']['value'] = True
    tow['variable_assignments']['inter_body_opening'] = {'kind': 'subject_behavior', 'value': None}
    tow['deliberate_differences'] = ['drawing_drawn_combination']
    tow['recording_description'] = json.loads((STAGE / towing['construction']).read_text())['recording_description']
    cases['cases'].append(tow)
    sweep_plan = json.loads((PACKAGE / 'cases/towing-sweep-plan.json').read_text())
    sweep = deepcopy(sweep_plan['spec'])
    sweep['status'] = 'complete'
    sweep.pop('missing_inputs', None)
    sweep['variable_assignments']['inter_body_opening'] = {'kind': 'subject_behavior', 'value': None}
    cases['sweep_specs'] = [sweep]
    template = json.loads((STAGE / 'proposals/template.json').read_text())
    template['parameter_refs'].append({
        'name': 'inter_body_opening', 'kind': 'subject_behavior',
        'range_or_domain': 'measured original complete-body opening'})
    (STAGE / 'proposals/template.json').write_text(json.dumps(template, indent=2) + '\n')
    observable_path = STAGE / 'proposals/judgment-observables.json'
    observable = json.loads(observable_path.read_text())
    observable['observable_requirements']['sweep_dimensions'].append({
        'name': 'inter_body_opening', 'unit': 'metres',
        'description': 'Measured opening between complete bodies on original frames.'})
    observable_path.write_text(json.dumps(observable, indent=2) + '\n')
    expand_sweeps(cases, templates=[template], bindings=bindings)
    expected = [PACKAGE.name + '__' + item['case_id']
                for item in sweep_plan['provisional_cases']]
    for item in cases['cases']:
        if item.get('sweep_id') == sweep['sweep_id']:
            item['case_id'] = PACKAGE.name + '__' + item['case_id']
    for item in cases['sweep_specs'][0]['selection_order']:
        if not item.startswith(sweep['sweep_id'] + '-'):
            raise ValueError('Unexpected runtime sweep selection')
    cases['sweep_specs'][0]['selection_order'] = [
        PACKAGE.name + '__' + item
        for item in cases['sweep_specs'][0]['selection_order']]
    expanded = [item['case_id'] for item in cases['cases'] if item.get('sweep_id') == sweep['sweep_id']]
    if expanded != expected:
        raise ValueError('Sweep grid case IDs or order changed')
    diagnostics = json.loads((PACKAGE / 'qualified-towing-sweep-manifest.json').read_text())
    for item in diagnostics['cases']:
        manifest['cases'].append({'case_id': item['case_id'], 'construction': item['construction'], 'kind': 'delivery'})
        target = STAGE / item['construction']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PACKAGE / item['construction'], target)
    cases_path.write_text(json.dumps(cases, indent=2) + '\n')
    index_path = STAGE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['template']['sha256'] = hashlib.sha256((STAGE / 'proposals/template.json').read_bytes()).hexdigest()
    for reference in index['stages']['judgment_observables']:
        if reference['path'] == 'proposals/judgment-observables.json':
            reference['sha256'] = hashlib.sha256(observable_path.read_bytes()).hexdigest()
    index['stages']['bindings']['sha256'] = hashlib.sha256(bindings_path.read_bytes()).hexdigest()
    index['stages']['cases']['sha256'] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    result = validate(STAGE, assignment, manifest)
    if result['selected_cases'] != 6:
        raise ValueError('Six selected cases required in staged draft')
    print(json.dumps({'format': 'worker-towing-semantic-diagnostic-proof',
                      'case_id': towing['case_id'], 'selected_cases': 6,
                      'sweep_case_ids': expanded,
                      'stage_count': result['stage_count'],
                      'canonical_delivery_unchanged': True}, sort_keys=True))


if __name__ == '__main__':
    main()
