"""Check the retained synthetic limo loading-purpose pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ('limo_at', 'limo_no_loading')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(reports):
    require(set(reports) == set(CASES), 'Exact loading comparison pair missing')
    fixed = []
    events = {}
    for suffix in CASES:
        report = reports[suffix]
        require(report.get('case_id') == ASSIGNMENT + '__' + suffix
                and report.get('candidate_id') == 'primary'
                and report.get('source_kind') == 'synthetic_native_sample'
                and report.get('physical_acceptance_claimed') is False
                and report.get('legal_verdict_claimed') is False,
                'Case identity or source limits differ')
        measures = report['measurements']
        observation = measures['signed_curb_observation']
        value = observation['value']
        require(value.get('source_kind') == 'synthetic_native_sample'
                and value.get('declared_service_class') == 'limo'
                and value.get('sign_present') is True
                and value.get('sign_over_red_extent') is True
                and value.get('red_curb_stationary_duration_s') == 1800.0
                and value.get('duration_relative_to_30_minutes') == 'at'
                and value.get('frames') == 36121,
                'Controlled limo duration, service, sign, or frames differ')
        require(measures['red_curb_stop_or_park_observed']['value'] is True
                and measures['four_view_frame_join']['value'] is True
                and measures['red_curb_extent']['value']['paint_color'] == 'red',
                'Red occupancy or camera join missing')
        require(value.get('statutory_exception_applies') is None
                and value.get('legal_verdict') is None,
                'Synthetic observation asserts a legal outcome')
        events[suffix] = value.get('recorded_activity_events')
        controlled = {k: v for k, v in value.items()
                      if k != 'recorded_activity_events'}
        fixed.append({'observation': controlled,
                      'actor_sha256': observation['sources']['native-raw-actors.jsonl'],
                      'map_sha256': observation['sources']['native-map-readback.json'],
                      'red_extent': measures['red_curb_extent'],
                      'red_occupancy': measures['red_curb_stop_or_park_observed'],
                      'four_view_join': measures['four_view_frame_join'],
                      'statute': measures['statute_source_context'],
                      'mail_clause': measures['mail_exception_source_text'],
                      'scope': measures['scope_red_occupancy']})
    require(fixed[0] == fixed[1], 'A controlled observation or source differs')
    require(isinstance(events['limo_at'], list)
            and len(events['limo_at']) == 1
            and events['limo_at'][0]['name'] == 'passenger_loading'
            and events['limo_at'][0]['duration_s'] > 0
            and events['limo_no_loading'] == [],
            'Loading activity distinction missing')
    return {'duration_s': 1800.0, 'frames': 36121,
            'at_recorded_activity': events['limo_at'],
            'no_loading_recorded_activity': events['limo_no_loading'],
            'fixed_source_hashes': {
                'native_actor_sha256': fixed[0]['actor_sha256'],
                'native_map_sha256': fixed[0]['map_sha256'],
                'statute_sha256': fixed[0]['statute']['sources']['statutory-context.json']}}


def main():
    manifest = HERE / 'execution-manifest.json'
    plan = HERE / 'case-plan.json'
    entries = {item['case_id']: item
               for item in json.loads(manifest.read_text())['cases']}
    comparison = next(item for item in json.loads(plan.read_text())['comparisons']
                      if item['comparison_id'].endswith('limo_loading_purpose'))
    require(comparison['case_ids'] == [ASSIGNMENT + '__' + suffix for suffix in CASES]
            and comparison['deliberate_differences'] == ['passenger_loading_event'],
            'Planned comparison differs')
    reports = {}
    sources = {}
    for suffix in CASES:
        stem = suffix.replace('_', '-')
        root = REPO / '.runtime-work' / f'c150142-current-{stem}-primary-saved-v1' / 'v0001'
        analysis = root / 'analysis/analysis-report.json'
        summary = HERE / f'current-{stem}-primary-saved-summary.json'
        audit = HERE / f'current-{stem}-primary-saved-audit.json'
        require(all(path.is_file() for path in (analysis, summary, audit)),
                'Retained selected source/report missing: ' + suffix)
        summary_data = json.loads(summary.read_text())
        audit_data = json.loads(audit.read_text())
        require(summary_data.get('passed') is True
                and audit_data.get('passed') is True
                and summary_data.get('case_id') == audit_data.get('case_id') == ASSIGNMENT + '__' + suffix
                and summary_data.get('processing_sha256') == audit_data.get('processing_sha256')
                and audit_data.get('manifest_sha256') == sha(manifest)
                and audit_data.get('construction_sha256') == entries[ASSIGNMENT + '__' + suffix]['construction_sha256'],
                'Selected processing/audit binding differs: ' + suffix)
        reports[suffix] = json.loads(analysis.read_text())
        sources[suffix] = {'analysis_sha256': sha(analysis),
                           'summary_sha256': sha(summary), 'audit_sha256': sha(audit),
                           'construction_sha256': audit_data['construction_sha256']}
    facts = check(reports)
    changed = json.loads(json.dumps(reports))
    changed['limo_no_loading']['measurements']['signed_curb_observation']['value']['declared_service_class'] = 'ordinary'
    try:
        check(changed)
    except ValueError as error:
        negative_control = str(error)
    else:
        raise AssertionError('Changed service class was accepted')
    changed = json.loads(json.dumps(reports))
    changed['limo_no_loading']['measurements']['signed_curb_observation']['value']['recorded_activity_events'] = facts['at_recorded_activity']
    try:
        check(changed)
    except ValueError as error:
        negative_activity = str(error)
    else:
        raise AssertionError('Missing loading distinction was accepted')
    receipt = {'format': 'c150142-limo-loading-saved-comparison-v1',
               'passed': True, 'source_kind': 'synthetic_native_sample',
               'comparison_id': comparison['comparison_id'],
               'manifest_sha256': sha(manifest), 'case_plan_sha256': sha(plan),
               'source_hashes': sources, 'facts': facts,
               'negative_changed_service_class': negative_control,
               'negative_missing_loading_distinction': negative_activity,
               'original_native_observed': False,
               'physical_acceptance_claimed': False, 'legal_verdict': None}
    destination = HERE / 'current-limo-loading-comparison-audit.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': comparison['comparison_id']}))


if __name__ == '__main__':
    main()
