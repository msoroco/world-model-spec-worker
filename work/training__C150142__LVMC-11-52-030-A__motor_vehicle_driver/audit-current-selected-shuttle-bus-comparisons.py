"""Audit current-runtime selected shuttle-bus saved boundary and loading pairs."""
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SAVED = {
    'shuttle_bus_below': 'saved-v1',
    'shuttle_bus_at': 'saved-v1',
    'shuttle_bus_above': 'saved-v1',
    'shuttle_bus_no_loading': 'saved-v1',
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def reject(check, reports, suffix, field, replacement):
    changed = json.loads(json.dumps(reports))
    changed[suffix]['measurements']['signed_curb_observation']['value'][field] = replacement
    try:
        check(changed)
    except ValueError as error:
        return str(error)
    raise AssertionError('Comparison accepted mutated ' + field)


def main():
    manifest = HERE / 'execution-manifest.json'
    plan = HERE / 'case-plan.json'
    manifest_data = json.loads(manifest.read_text())
    entries = {e['case_id']: e for e in manifest_data['cases']}
    comparisons = json.loads(plan.read_text())['comparisons']
    reports, bindings = {}, {}
    for suffix, saved_name in SAVED.items():
        root = REPO / '.runtime-work/owner150142/long-selected-v1' / suffix / saved_name / 'v0001'
        proof_path = HERE / f'current-{suffix.replace("_", "-")}-primary-selected-saved-proof.json'
        proof = json.loads(proof_path.read_text())
        processing = root / 'processing.json'
        analysis = root / 'analysis/analysis-report.json'
        case_id = HERE.name + '__' + suffix
        assert proof['case_id'] == case_id
        assert proof['selected_manifest_sha256'] == sha(manifest)
        assert proof['runtime_manifest_sha256'] == manifest_data['runtime_manifest_sha256']
        assert proof['processing_sha256'] == sha(processing)
        assert proof['analysis_report_sha256'] == sha(analysis)
        assert proof['timestamp_joins']['passed'] and proof['source_preserved']
        assert proof['final_video']['passed']
        source = json.loads(processing.read_text())
        assert source['analysis_revision']['construction_sha256'] == entries[case_id]['construction_sha256']
        assert source['passed'] and source['recorded_only'] and not source['missing_evidence']
        reports[suffix] = json.loads(analysis.read_text())
        bindings[suffix] = {'proof_sha256': sha(proof_path),
                            'processing_sha256': sha(processing),
                            'analysis_sha256': sha(analysis),
                            'construction_sha256': entries[case_id]['construction_sha256']}
    boundary = runpy.run_path(str(HERE / 'audit-shuttle-bus-boundary-comparison.py'))['check']
    loading = runpy.run_path(str(HERE / 'audit-shuttle-bus-loading-comparison.py'))['check']
    boundary_cases = {k: reports[k] for k in ('shuttle_bus_below', 'shuttle_bus_at', 'shuttle_bus_above')}
    loading_cases = {k: reports[k] for k in ('shuttle_bus_at', 'shuttle_bus_no_loading')}
    boundary_facts = boundary(boundary_cases)
    loading_facts = loading(loading_cases)
    boundary_id = next(x['comparison_id'] for x in comparisons if x['comparison_id'].endswith('shuttle_bus_30min_boundary'))
    loading_id = next(x['comparison_id'] for x in comparisons if x['comparison_id'].endswith('shuttle_bus_loading_purpose'))
    receipt = {'format': 'c150142-current-selected-shuttle-bus-comparisons-v1',
               'passed': True, 'selected_manifest_sha256': sha(manifest),
               'runtime_manifest_sha256': manifest_data['runtime_manifest_sha256'],
               'case_plan_sha256': sha(plan), 'source_bindings': bindings,
               'boundary': {'comparison_id': boundary_id, 'facts': boundary_facts,
                            'changed_service_rejected': reject(boundary, boundary_cases,
                                'shuttle_bus_at', 'declared_service_class', 'ordinary')},
               'loading': {'comparison_id': loading_id, 'facts': loading_facts,
                           'changed_service_rejected': reject(loading, loading_cases,
                                'shuttle_bus_no_loading', 'declared_service_class', 'ordinary'),
                           'missing_activity_distinction_rejected': reject(loading, loading_cases,
                                'shuttle_bus_no_loading', 'recorded_activity_events',
                                loading_facts['at_recorded_activity'])},
               'original_native_observed': False, 'physical_acceptance_claimed': False,
               'legal_verdict': None}
    output = HERE / 'current-selected-shuttle-bus-comparison-audit.json'
    output.write_text(json.dumps(receipt, sort_keys=True, separators=(',', ':')))
    print(json.dumps({'receipt': output.name, 'sha256': sha(output),
                      'comparisons': 2}, sort_keys=True))


if __name__ == '__main__':
    main()
