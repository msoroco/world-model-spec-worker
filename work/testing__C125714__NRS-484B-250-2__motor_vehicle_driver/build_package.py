"""Freeze the qualitative same-time arrival experiment as explicit exact cases."""
import copy
import hashlib
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
CANDIDATE = REPO / 'migration-candidates' / AID
sys.path.insert(0, str(REPO / 'runtime/main-pipeline-v1/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    old = json.loads((CANDIDATE / 'case-plan.json').read_text())
    assert old['law_id'] == assignment['law']['id'] == 'NRS-484B-250-2'
    assert old['cell_id'] == assignment['cell_id']
    assert len(old['cases']) == 1 and old['cases'][0]['target_type'] == 'baseline'
    baseline = old['cases'][0]
    assignments = copy.deepcopy(baseline['variable_assignments'])
    assignments['test_branch']['value'] = 'arrival_offset_sweep'
    assignments['commanded_release_offset_s']['value'] = 0.0
    assignments['commanded_release_delay_s'] = {'kind': 'controller', 'value': 1.0, 'unit': 's'}
    assignments['highway_context']['value']['administrative_status'] = 'explicit synthetic public-highway and no-official-control assumptions'
    sweep = {'sweep_id': AID + '__release_delay', 'target_law_id': assignment['law']['id'],
        'judgment_refs': [{'phrase': 'approximately the same time', 'note': 'Unresolved qualitative entry simultaneity'}],
        'status': 'complete', 'mode': 'one_dimensional',
        'rationale': 'Fixed ego release delay; measure both full-footprint crossing-entry times without deciding approximate simultaneity',
        'axes': [{'variable': 'commanded_release_delay_s', 'unit': 's', 'min': 1.0, 'max': 5.0, 'spacing': 1.0,
                  'observable': 'entry_time_difference_s',
                  'range_rationale': 'Fixed 1-5s controller-release range fits a 30s episode and spans likely entry ordering; actual timing unverified',
                  'spacing_rationale': 'One-second release increments exceed 0.05s source sampling without setting a legal tolerance',
                  'feasibility_evidence': 'Controller accepts finite release delays; physical timing is the purpose of capability measurement',
                  'measurement': {'method': 'difference of original 20Hz full-body entry-bracket midpoints; retain both brackets',
                                  'time_window': 'full approach through both crossing entries', 'statistic': 'first'}}],
        'landmarks': [], 'variable_assignments': assignments,
        'recording_description': baseline['recording_description']}
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'cases': [baseline], 'sweep_specs': [sweep]}
    expand_sweeps(proposal, templates=(), bindings=None)
    cases = proposal['cases']
    old['cases'] = cases
    old['comparisons'] = []
    old['sources'] = [{'path': rel, 'sha256': sha(REPO / rel)} for rel in [
        'inputs/' + AID + '/assignment.json', 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'runtime/main-pipeline-v1/scenario_pipeline/worker_exchange/execution_manifest.py',
        'updates/004.json', 'skills/scenario-coverage-cases/SKILL.md']]
    old['runtime_uncertainties'] = ['Actual entry-time difference and its sample bracket are unmeasured.',
        'Native crossing/median mesh, actor paths, camera visibility, and duration need first-run evidence.',
        'The phrase approximately the same time remains unresolved; no legal timing tolerance is authored.']
    write(FOLDER / 'case-plan.json', old)
    write(FOLDER / 'proposals/cases.json', proposal)
    base = json.loads((CANDIDATE / 'config.json').read_text())
    base['supported_case_ids'] = [c['case_id'] for c in cases]
    base['required_atoms'] = [o['name'] for o in old['observations'] if o.get('mandatory', True)]
    base['max_ticks'] = 600
    base['implementation_gaps'] = []
    base['authored_test_context'] = {'core_assumptions': [
        'Public vehicular access and highway dedication are explicit synthetic assumptions.',
        'Both participants approach the same southern crossing from different highways.',
        'No official control device is authored at the target intersection.']}
    files = ['runner.py', 'scenario.py', 'source_audit.py', 'analyze.py', 'tests/test_crossing.py']
    entries = []
    for case in cases[1:]:
        cfg = copy.deepcopy(base)
        cfg['case'] = case
        cfg['selected_case_id'] = case['case_id']
        construction = {'case_id': case['case_id'], 'cell_id': assignment['cell_id'],
            'actor': assignment['actor'], 'entrypoint': 'runner.py',
            'recording_description': case['recording_description'],
            'measurement_plan': {'source': 'participants.jsonl', 'observable': 'ego entry bracket minus other entry bracket',
                                 'sampling_hz': 20, 'uncertainty_s': .05, 'judgment_cutoff': None},
            'static_checks': ['OpenDRIVE crossing links', 'no signal inventory', 'route continuity', 'four camera formats'],
            'termination_rules': {'max_ticks': 600, 'success': 'both participant paths completed', 'failure': 'timeout or capture error'},
            'mechanisms': {'builder': 'scenario.py authored OpenDRIVE',
                           'controllers': 'native VehicleControl, fixed release delay and other speed',
                           'capture': 'supplied PipelineCapture and original observations',
                           'video': 'four FFV1 Matroska cameras with source pixel hashes'},
            'files': [{'path': f, 'content': (FOLDER / f).read_text(), 'source': 'work/' + AID + '/' + f}
                      for f in files] + [{'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'}]}
        rel = 'constructions/' + case['case_id'] + '.json'
        write(FOLDER / rel, construction)
        if case is cases[1]:
            write(FOLDER / 'config.json', cfg)
            write(FOLDER / 'construction.json', construction)
        entries.append({'case_id': case['case_id'], 'kind': 'capability', 'construction': rel,
                        'construction_sha256': sha(FOLDER / rel),
                        'measurement_procedure': {'entrypoint': 'analyze.py',
                                                  'output_schema': 'same-time-crossing-capability-v1'}})
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
          'assignment_id': AID,
          'runtime_manifest_sha256': sha(REPO / 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
          'cases': entries})


if __name__ == '__main__':
    main()
