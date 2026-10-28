"""Freeze two one-way travel-direction capability cases."""
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
    plan = json.loads((CANDIDATE / 'case-plan.json').read_text())
    assert assignment['law']['id'] == plan['law_id'] == 'NRS-484B-220-1'
    assert [c['target_type'] for c in plan['cases']] == ['baseline', 'compliant_attempt', 'violating_attempt']
    cases = copy.deepcopy(plan['cases'])
    for case in cases:
        case['variable_assignments']['highway_context']['value']['administrative_status'] = 'explicit synthetic public-way and direction-designation assumptions'
    plan['cases'] = cases
    plan['sources'] = [{'path': rel, 'sha256': sha(REPO / rel)} for rel in [
        'inputs/' + AID + '/assignment.json', 'runtime/main-pipeline-v1/SOURCE-MANIFEST.json',
        'updates/004.json', 'skills/scenario-coverage-cases/SKILL.md']]
    plan['runtime_uncertainties'] = ['Native OneWay landmark may not render as a visible sign.',
        'Governed multilane extent, physical driver direction, footprint, and video visibility need original capture.',
        'Public-way and sign designation remain explicit synthetic assumptions.']
    write(FOLDER / 'case-plan.json', plan)
    write(FOLDER / 'proposals/cases.json', {'status': 'draft', 'cell_id': assignment['cell_id'],
        'actor': assignment['actor'], 'cases': cases, 'sweep_specs': [], 'sweeps_expanded': True})
    base = json.loads((CANDIDATE / 'config.json').read_text())
    base['supported_case_ids'] = [c['case_id'] for c in cases]
    base['required_atoms'] = [o['name'] for o in plan['observations'] if o.get('mandatory', True)]
    base['max_ticks'] = 600
    base['implementation_gaps'] = []
    base['authored_test_context'] = {'core_assumptions': [
        'Public-way status and official designation are explicit synthetic assumptions.',
        'The two right-side OpenDRIVE lanes are designated eastbound.',
        'The OneWay OpenDRIVE signal is authored but rendering and governance require original native evidence.']}
    files = ['runner.py', 'scenario.py', 'source_audit.py', 'analyze.py', 'tests/test_oneway.py']
    entries = []
    for case in cases[1:]:
        cfg = copy.deepcopy(base)
        cfg['case'] = case
        cfg['selected_case_id'] = case['case_id']
        construction = {'case_id': case['case_id'], 'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
            'entrypoint': 'runner.py', 'recording_description': case['recording_description'],
            'measurement_plan': {'source': 'physical_samples.jsonl', 'observable': 'measured longitudinal displacement',
                'reference': 'eastbound native x; full body vertices and landmark inventory retained'},
            'static_checks': ['two same-direction driving lanes', 'direction signal authored', 'route continuity', 'camera formats'],
            'termination_rules': {'max_ticks': 600, 'success': 'selected route endpoint reached', 'failure': 'timeout or capture error'},
            'mechanisms': {'builder': 'scenario.py OpenDRIVE', 'controller': 'native VehicleControl route follower',
                'capture': 'supplied PipelineCapture with original observations',
                'video': 'four lossless FFV1 Matroska source views with frame/pixel hashes'},
            'files': [{'path': f, 'content': (FOLDER/f).read_text(), 'source': 'work/'+AID+'/'+f} for f in files] +
                     [{'path': 'config.json', 'content': json.dumps(cfg, indent=2)+'\n'}]}
        rel = 'constructions/'+case['case_id']+'.json'
        write(FOLDER/rel, construction)
        if case is cases[1]:
            write(FOLDER/'config.json', cfg)
            write(FOLDER/'construction.json', construction)
        entries.append({'case_id': case['case_id'], 'kind': 'capability', 'construction': rel,
            'construction_sha256': sha(FOLDER/rel),
            'measurement_procedure': {'entrypoint': 'analyze.py', 'output_schema': 'one-way-direction-capability-v1'}})
    write(FOLDER/'execution-manifest.json', {'format': 'worker-execution-manifest-v1',
        'assignment_id': AID, 'runtime_manifest_sha256': sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),
        'cases': entries})


if __name__ == '__main__':
    main()
