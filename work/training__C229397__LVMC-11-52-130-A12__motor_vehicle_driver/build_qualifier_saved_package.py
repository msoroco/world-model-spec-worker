"""Isolate qualifier saved-processing diagnostics from selected delivery cases."""
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PACKAGE = HERE / 'qualifier-saved-package'
SUFFIXES = ('traffic_conflict_near', 'device_direction_near')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((HERE / 'execution-manifest.json').read_text())
    existing = json.loads((HERE / 'proposals/cases.json').read_text())
    base = next(case for case in existing['cases'] if case['case_id'].endswith('__controlled_2'))
    cases = []
    proposals = []
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        source = HERE / 'draft-qualifiers' / suffix / 'primary/construction.json'
        target = PACKAGE / 'constructions' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        construction = json.loads(target.read_text())
        proposal = json.loads(json.dumps(base))
        proposal['case_id'] = case_id
        proposal['target_type'] = 'diagnostic_qualifier_probe'
        proposal['paired_probe_id'] = 'c229397_parking_qualifier_' + suffix
        proposal['deliberate_differences'] = [suffix]
        proposal['probe']['primary_variable'] = suffix
        proposal['probe']['target_value_or_branch'] = suffix
        proposal['variable_assignments'][suffix] = {'kind': 'controller', 'value': suffix}
        proposal['recording_description'] = construction['recording_description']
        proposal['unresolved_judgment_calls'] = [
            'marked-crosswalk status and statutory qualifier applicability']
        proposals.append(proposal)
        cases.append({'case_id': case_id, 'kind': 'diagnostic_qualifier_candidate',
                      'construction': str(target.relative_to(PACKAGE)),
                      'construction_sha256': sha(target), 'id': 'primary',
                      'measurement_procedure': {'entrypoint': 'finalize_delivery.py'},
                      'delivery_readiness': 'incomplete'})
    PACKAGE.mkdir(exist_ok=True)
    (PACKAGE / 'proposals').mkdir(exist_ok=True)
    (PACKAGE / 'proposals/cases.json').write_text(json.dumps({
        'cell_id': 'C229397', 'actor': 'motor_vehicle_driver',
        'status': 'diagnostic_unselected_qualifier_candidates',
        'cases': proposals}, indent=2) + '\n')
    manifest = {'format': 'worker-execution-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': selected['runtime_manifest_sha256'],
                'status': 'partial_unselected_qualifier_saved_proof',
                'cases': cases}
    path = PACKAGE / 'execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(path.relative_to(HERE)), 'sha256': sha(path),
                      'case_count': len(cases)}, sort_keys=True))


if __name__ == '__main__':
    main()
