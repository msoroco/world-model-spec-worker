"""Independent comparison of three retained synthetic limo saved reports."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ('limo_below', 'limo_at', 'limo_above')
VERSIONS = {'limo_below': 'v1', 'limo_at': 'v1', 'limo_above': 'v1'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def check(values):
    require(set(values) == set(CASES), 'Exact three-case boundary missing')
    reduced = {}
    for suffix in CASES:
        data = values[suffix]
        require(data.get('case_id') == ASSIGNMENT + '__' + suffix
                and data.get('candidate_id') == 'primary'
                and data.get('source_kind') == 'synthetic_native_sample',
                'Case identity or source provenance differs')
        observations = data['measurements']['signed_curb_observation']
        value = observations['value']
        require(value.get('source_kind') == 'synthetic_native_sample'
                and value.get('declared_service_class') == 'limo'
                and value.get('sign_present') is True
                and value.get('sign_over_red_extent') is True,
                'Controlled service/sign condition differs')
        require(data['measurements']['red_curb_stop_or_park_observed']['value'] is True
                and data['measurements']['four_view_frame_join']['value'] is True,
                'Curb or camera observation missing')
        require(value.get('recorded_activity_events')
                and value['recorded_activity_events'][0]['name'] == 'passenger_loading',
                'Passenger activity condition differs')
        require(value.get('duration_relative_to_30_minutes') == suffix.removeprefix('limo_'),
                'Recorded boundary side differs')
        fixed = {k: value[k] for k in ('displayed_sign_classes', 'sign_center_x_m',
                 'native_blueprint', 'declared_service_class', 'mailbox_present',
                 'recorded_activity_events')}
        fixed['red_curb_extent'] = data['measurements']['red_curb_extent']['value']
        fixed['native_map_sha256'] = observations['sources']['native-map-readback.json']
        fixed['statute_sha256'] = data['measurements']['statute_source_context']['sources']['statutory-context.json']
        reduced[suffix] = {'duration_s': value['red_curb_stationary_duration_s'],
                           'frames': value['frames'], 'fixed': fixed}
    require(reduced['limo_below']['fixed'] == reduced['limo_at']['fixed']
            == reduced['limo_above']['fixed'],
            'Comparison changed a fixed source condition')
    durations = [reduced[c]['duration_s'] for c in CASES]
    require(durations[0] < 1800 and durations[1] == 1800 and durations[2] > 1800,
            'Measured 30-minute boundary not bracketed')
    require([reduced[c]['frames'] for c in CASES] == [36120, 36121, 36122],
            'Full duration frame coverage differs')
    return {'duration_s': dict(zip(CASES, durations)),
            'frames': {case: reduced[case]['frames'] for case in CASES},
            'fixed_context': reduced[CASES[0]]['fixed']}


def main():
    manifest = HERE / 'execution-manifest.json'
    plan = HERE / 'case-plan.json'
    entries = {c['case_id']: c for c in json.loads(manifest.read_text())['cases']}
    comparisons = json.loads(plan.read_text())['comparisons']
    exact = next(c for c in comparisons if c['comparison_id'].endswith('limo_30min_boundary'))
    require(exact['case_ids'] == [ASSIGNMENT + '__' + suffix for suffix in CASES],
            'Planned case order differs')
    reports = {}
    sources = {}
    for suffix in CASES:
        result = REPO / '.runtime-work' / f'c150142-current-{suffix.replace("_", "-")}-primary-saved-{VERSIONS[suffix]}' / 'v0001'
        analysis = result / 'analysis/analysis-report.json'
        summary = HERE / f'current-{suffix.replace("_", "-")}-primary-saved-summary.json'
        audit = HERE / f'current-{suffix.replace("_", "-")}-primary-saved-audit.json'
        require(all(p.is_file() for p in (analysis, summary, audit)),
                'Retained selected source/report missing: ' + suffix)
        summary_data = json.loads(summary.read_text())
        audit_data = json.loads(audit.read_text())
        require(summary_data.get('passed') is True and audit_data.get('passed') is True
                and summary_data.get('case_id') == audit_data.get('case_id') == ASSIGNMENT + '__' + suffix
                and summary_data.get('processing_sha256') == audit_data.get('processing_sha256')
                and audit_data.get('manifest_sha256') == sha(manifest)
                and audit_data.get('construction_sha256') == entries[ASSIGNMENT + '__' + suffix]['construction_sha256'],
                'Selected processing/audit source binding differs: ' + suffix)
        reports[suffix] = json.loads(analysis.read_text())
        sources[suffix] = {'analysis_sha256': sha(analysis), 'summary_sha256': sha(summary),
                           'audit_sha256': sha(audit),
                           'construction_sha256': audit_data['construction_sha256']}
    facts = check(reports)
    negative = json.loads(json.dumps(reports))
    negative['limo_at']['measurements']['signed_curb_observation']['value']['declared_service_class'] = 'ordinary'
    try:
        check(negative)
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError('Changed fixed service class accepted')
    receipt = {'format': 'c150142-limo-boundary-saved-comparison-v1',
               'passed': True, 'source_kind': 'synthetic_native_sample',
               'comparison_id': exact['comparison_id'],
               'manifest_sha256': sha(manifest), 'case_plan_sha256': sha(plan),
               'source_hashes': sources, 'facts': facts,
               'negative_changed_service_class': rejection,
               'original_native_observed': False, 'physical_acceptance_claimed': False,
               'legal_verdict': None}
    destination = HERE / 'current-limo-boundary-comparison-audit.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'durations': facts['duration_s']}))


if __name__ == '__main__':
    main()
