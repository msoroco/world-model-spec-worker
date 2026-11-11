"""Build source-bound selected CPU packages without claiming Native realization."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def build():
    draft = json.loads((HERE/'draft-execution-manifest.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    proposal = json.loads((HERE/'proposals/cases.json').read_text())
    exact = {row['case_id'] for row in plan['cases']}
    if (draft['assignment_id'] != HERE.name or len(draft['cases']) != 2 or
            exact != {row['case_id'] for row in draft['cases']} or
            exact != {row['case_id'] for row in proposal['cases']}):
        raise ValueError('Exact source-reviewed case pair differs')
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'status': 'partial_selected_cpu_proofs_pending_physical_unverified',
                'runtime_manifest_sha256': sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
                'source_branch': 'stop_or_stand_at_driveway', 'cases': []}
    for entry in draft['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        selected = {key: entry[key] for key in ('case_id', 'candidate_risk',
            'measurement_contract', 'measurement_procedure', 'fixture_recipe')}
        selected.update(kind='delivery', candidates=[],
            native_handoff={'python_env_var': 'CARLA_PYTHON',
                            'host_env_var': 'CARLA_HOST',
                            'port_env_var': 'CARLA_PORT'},
            preparation_status='selected_for_CPU_proof; original Native evidence unverified')
        for candidate in NAMES:
            source = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            construction = json.loads((HERE/source['construction']).read_text())
            if sha(HERE/source['construction']) != source['construction_sha256']:
                raise ValueError('Draft construction changed: '+candidate)
            config_items = [item for item in construction['files'] if item['path'] == 'config.json']
            if len(config_items) != 1:
                raise ValueError('Exactly one selected config required')
            config = json.loads(config_items[0]['content'])
            if (config['case']['case_id'] != entry['case_id'] or
                    config['case']['recording_description'] != construction['recording_description']):
                raise ValueError('Selected case recording contract differs')
            config['status'] = 'selected_cpu_construction_physical_unverified'
            config_items[0]['content'] = json.dumps(config, indent=2)+'\n'
            construction['status'] = 'selected_cpu_construction_physical_unverified'
            construction['measurement_plan']['status'] = 'cpu_software_compatible_physical_unverified'
            construction['selection_source'] = {
                'draft_construction': source['construction'],
                'draft_construction_sha256': source['construction_sha256'],
                'case_plan_sha256': sha(HERE/'case-plan.json')}
            relative = f'selected-candidates/{suffix}/{candidate}/construction.json'
            path = HERE/relative
            write(path, construction)
            row = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(path)}
            if candidate == 'primary':
                selected.update(construction=relative,
                                construction_sha256=row['construction_sha256'])
            else:
                row.update(trigger=source['trigger'], changed_knobs=source['changed_knobs'])
                selected['candidates'].append(row)
        manifest['cases'].append(selected)
    write(HERE/'execution-manifest.json', manifest)
    return {'selected_cases': len(manifest['cases']),
            'candidate_constructions': sum(1+len(row['candidates']) for row in manifest['cases']),
            'status': manifest['status']}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
