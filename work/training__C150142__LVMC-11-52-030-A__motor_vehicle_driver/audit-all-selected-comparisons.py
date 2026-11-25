"""Join the 18 selected synthetic comparison audits without rerunning decodes."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERVICES = ('tour-bus', 'shuttle-bus', 'limo', 'rtc-bus')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit():
    manifest_sha = sha(HERE / 'execution-manifest.json')
    plan = read('case-plan.json')
    expected = {row['comparison_id']: set(row['case_ids'])
                for row in plan['comparisons']}
    require(len(expected) == 18, 'Selected comparison plan differs')
    sources = {}

    def add(cid, case_ids, name, report):
        require(cid in expected and cid not in sources,
                'Unknown or repeated selected comparison')
        require(set(case_ids) == expected[cid],
                'Selected comparison cases differ: ' + cid)
        require(report['passed'] is True and
                report['manifest_sha256'] == manifest_sha and
                report.get('source_kind') == 'synthetic_native_sample' and
                report.get('physical_acceptance_claimed') is False and
                report.get('legal_acceptance_claimed', False) is False and
                report.get('legal_verdict') is None,
                'Selected source comparison is stale or overclaims: ' + cid)
        sources[cid] = {'receipt': name, 'sha256': sha(HERE / name)}

    ordinary_name = 'current-ordinary-comparison-audit.json'
    ordinary = read(ordinary_name)
    require(ordinary.get('original_native_observed') is False,
            'Ordinary source provenance differs')
    for row in ordinary['comparisons']:
        add(row['comparison_id'], row['case_ids'], ordinary_name, ordinary)

    for service in SERVICES:
        name = 'current-selected-' + service + '-comparison-audit.json'
        report = read(name)
        require(report.get('passed') is True and
                report.get('selected_manifest_sha256') == manifest_sha and
                report.get('case_plan_sha256') == sha(HERE / 'case-plan.json') and
                report.get('original_native_observed') is False and
                report.get('physical_acceptance_claimed') is False and
                report.get('legal_verdict') is None,
                'Current selected long comparison differs: ' + service)
        slug = service.replace('-', '_')
        bindings = report['source_bindings']
        require(set(bindings) == {slug + '_' + suffix for suffix in
                ('below', 'at', 'above', 'no_loading')},
                'Current selected long proof set differs: ' + service)
        for suffix, source in bindings.items():
            proof_name = ('current-' + service + '-' +
                          suffix[len(slug)+1:].replace('_', '-') +
                          '-primary-selected-saved-proof.json')
            require(sha(HERE / proof_name) == source['proof_sha256'],
                    'Current selected saved proof changed: ' + suffix)
        for kind in ('boundary', 'loading'):
            branch = report[kind]
            require(bool(branch.get('changed_service_rejected')) and
                    (kind != 'loading' or bool(branch.get('missing_activity_distinction_rejected'))),
                    'Current selected long negative mutation missing')
            cases = [HERE.name + '__' + slug + '_' + suffix for suffix in
                     (('below', 'at', 'above') if kind == 'boundary'
                      else ('at', 'no_loading'))]
            add(branch['comparison_id'], cases, name,
                {'passed': True, 'manifest_sha256': report['selected_manifest_sha256'],
                 'source_kind': 'synthetic_native_sample',
                 'physical_acceptance_claimed': False,
                 'legal_acceptance_claimed': False, 'legal_verdict': None})

    short_name = 'current-short-exception-comparison-audit.json'
    short = read(short_name)
    for row in short['rows']:
        require(row['source_contrast_passed'] is True and
                row.get('original_native_observed') is False and
                row.get('legal_verdict') is None,
                'Short source comparison failed')
        add(row['comparison_id'],
            [source['case_id'] for source in row['source_observations']],
            short_name, short)
    require(set(sources) == set(expected), 'Selected comparison audit missing')
    return {'format': 'c150142-all-selected-comparison-index-v1',
            'passed': True, 'selected_comparisons': len(sources),
            'manifest_sha256': manifest_sha, 'case_plan_sha256': sha(HERE / 'case-plan.json'),
            'source_kind': 'synthetic_native_sample', 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'comparisons': sources}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
