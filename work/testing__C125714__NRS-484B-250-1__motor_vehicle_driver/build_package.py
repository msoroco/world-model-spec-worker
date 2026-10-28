"""Freeze exact crossing cases against the supplied runtime manifest."""
import copy
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
CANDIDATE = REPO / 'migration-candidates' / AID


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    old = json.loads((CANDIDATE / 'case-plan.json').read_text())
    assert old['law_id'] == assignment['law']['id']
    assert old['cell_id'] == assignment['cell_id']
    assert [c['target_type'] for c in old['cases']] == ['baseline', 'compliant_attempt', 'violating_attempt']
    old['sources'] = [{'path': rel, 'sha256': sha(REPO / rel)} for rel in [
        'inputs/' + AID + '/assignment.json', 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'runtime/main-pipeline-v1/scenario_pipeline/worker_exchange/execution_manifest.py',
        'updates/004.json', 'skills/worker-preparation/SKILL.md']]
    old['runtime_uncertainties'] = ['Native crossing/median geometry and map connectivity require a live readback.',
        'Relative full-footprint entry timing, yield response, completion, visibility and duration remain unmeasured.',
        'Public vehicular access is an explicit synthetic assumption; no physical observation proves it.']
    write(FOLDER / 'case-plan.json', old)
    cases = copy.deepcopy(old['cases'])
    proposal = {'status': 'draft', 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                'cases': cases, 'sweep_specs': [], 'sweeps_expanded': True}
    write(FOLDER / 'proposals/cases.json', proposal)
    base = json.loads((CANDIDATE / 'config.json').read_text())
    base['supported_case_ids'] = [c['case_id'] for c in cases]
    base['required_atoms'] = [o['name'] for o in old['observations'] if o.get('mandatory', True)]
    base['max_ticks'] = 600
    base['implementation_gaps'] = []
    base['authored_test_context'] = {'core_assumptions': [
        'Public vehicular access and highway dedication are explicit synthetic assumptions.',
        'The two crossings are distinct; this case targets the southern crossing only.',
        'No official control devices are authored at the targeted crossing.']}
    files = ['runner.py', 'scenario.py', 'source_audit.py', 'analyze.py', 'tests/test_crossing.py']
    for case in cases[1:]:
        cfg = copy.deepcopy(base)
        cfg['case'] = case
        cfg['selected_case_id'] = case['case_id']
        construction = {'case_id': case['case_id'], 'cell_id': assignment['cell_id'],
            'actor': assignment['actor'], 'entrypoint': 'runner.py',
            'recording_description': case['recording_description'],
            'measurement_plan': {'source': 'participants.jsonl', 'method': 'native full-body crossing occupancy brackets',
                                 'sampling_hz': 20, 'uncertainty_s': .05},
            'static_checks': ['OpenDRIVE links and no signal inventory', 'route continuity', 'capture channels', 'four camera formats'],
            'termination_rules': {'max_ticks': 600, 'success': 'both participant paths completed',
                                  'failure': 'timeout or captured error'},
            'mechanisms': {'builder': 'scenario.py authored OpenDRIVE',
                           'controllers': 'native VehicleControl for ego and other vehicle',
                           'capture': 'supplied PipelineCapture; all original native actors',
                           'video': 'four FFV1 Matroska cameras with native frame mapping'},
            'files': [{'path': f, 'content': (FOLDER / f).read_text(),
                       'source': 'work/' + AID + '/' + f} for f in files] +
                     [{'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'}]}
        rel = 'constructions/' + case['case_id'] + '.json'
        write(FOLDER / rel, construction)
        if case is cases[1]:
            write(FOLDER / 'config.json', cfg)
            write(FOLDER / 'construction.json', construction)
    entries = []
    for case in cases[1:]:
        rel = 'constructions/' + case['case_id'] + '.json'
        entries.append({'case_id': case['case_id'], 'kind': 'capability', 'construction': rel,
                        'construction_sha256': sha(FOLDER / rel),
                        'measurement_procedure': {'entrypoint': 'analyze.py',
                                                  'output_schema': 'prior-entry-capability-v1'}})
    write(FOLDER / 'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
          'assignment_id': AID,
          'runtime_manifest_sha256': sha(REPO / 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
          'cases': entries})


if __name__ == '__main__':
    main()
