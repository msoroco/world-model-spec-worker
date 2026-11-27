"""Bind six additional exact Native bus branch variants to the partial manifest."""
import hashlib
import json
from pathlib import Path
from build_variant_diagnostic import VARIANTS

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    template = json.loads((ROOT / 'cases/designated_terminus/construction.json').read_text())
    existing = {e['case_id']: e for e in manifest['cases']}
    all_cases = [AID + '__' + suffix for suffix in
                 ('designated_terminus', 'undesignated_street', *VARIANTS)]
    for suffix, (kind, _) in VARIANTS.items():
        case = AID + '__' + suffix
        construction = json.loads(json.dumps(template))
        construction['case_id'] = case
        files = {entry['path']: entry for entry in construction['files']}
        for target, source in (('runner.py', 'variant_runner.py'),
                               ('geometry.py', 'variant_geometry.py'),
                               ('analysis/bus_standing.py', 'variant_bus_standing.py')):
            files[target]['content'] = (ROOT / source).read_text()
            files[target].pop('source', None)
        config = json.loads(files['config.json']['content'])
        config.update(case_id=case, selected_case_id=case, supported_case_ids=all_cases,
                      requested_location=kind)
        config['case'] = {'case_id': case}
        files['config.json']['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        construction['files'] = list(files.values())
        path = ROOT / 'cases' / suffix / 'construction.json'
        write(path, construction)
        existing[case] = {'case_id': case, 'kind': 'delivery',
                          'construction': str(path.relative_to(ROOT)),
                          'construction_sha256': sha(path),
                          'candidate_risk': {'status': 'physical',
                            'reason': 'Bus parking-lane spawn or brake position may fail in Native CARLA.'},
                          'candidates': [], 'delivery_readiness': 'incomplete',
                          'measurement_procedure': {'entrypoint': 'finalize.py'},
                          'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
    manifest['cases'] = list(existing.values())
    write(MANIFEST, manifest)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for disposition in plan['requirement_dispositions']:
        disposition['case_ids'] = all_cases
    for item in plan['cases']:
        if item['case_id'] in all_cases:
            item['selected'] = True
            item['planning_status'] = 'selected_cpu_construction_physical_unverified'
    write(plan_path, plan)
    print('Eight exact bus cases bound; six new variants need proof')


if __name__ == '__main__':
    main()
