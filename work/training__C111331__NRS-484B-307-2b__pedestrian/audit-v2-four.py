"""Independently audit four CPU diagnostics and two controlled comparisons.

This audit never calls a synthetic packet an original physical observation.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
FIXED = ('cell_id', 'law_id', 'actor', 'entrypoint', 'recording_description')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit_case(case, root=HERE):
    suffix = case['case_id'].rsplit('__', 1)[-1]
    if suffix not in EXPECTED:
        raise ValueError('Unknown exact case')
    bundle = root / 'v2-primary' / suffix
    proof = bundle / 'proofs'
    construction = read(bundle / 'construction.json')
    config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    compatible = read(proof / 'compatibility.json')
    saved = read(proof / 'processing.json')
    report = read(proof / 'analysis-report.json')
    selection = read(proof / 'candidate-selection.json')
    if sha(bundle / 'construction.json') != case['construction_sha256'] or config['case_id'] != case['case_id']:
        raise ValueError('Construction identity or bytes differ')
    if not compatible['passed'] or compatible['construction_sha256'] != case['construction_sha256']:
        raise ValueError('Positive compatibility binding differs')
    needed = {'native_validation', 'lean_decoder', 'render', 'final_decode',
              'selected_measurements', 'negative_case_source', 'four_camera_sources'}
    if not needed <= set(compatible['checks']):
        raise ValueError('Public positive or negative checks missing')
    if compatible['fixture_recipe_sha256'] != sha(bundle / 'recipe.json') or \
            compatible['measurement_contract_sha256'] != sha(bundle / 'measurement-contract.json') or \
            compatible['analysis_report_sha256'] != sha(proof / 'analysis-report.json') or \
            compatible['negative_log_sha256'] != sha(proof / 'negative-analysis.log'):
        raise ValueError('Compatibility source hash differs')
    if compatible['negative_error_contains'] not in (proof / 'negative-analysis.log').read_text():
        raise ValueError('Missing-source rejection absent')
    if selection['candidate_id'] != 'primary' or selection['construction_sha256'] != case['construction_sha256']:
        raise ValueError('Candidate selection differs')
    if saved['case_id'] != case['case_id'] or not saved['recorded_only'] or saved['missing_evidence'] or \
            saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed'] or \
            'originals_verified' not in saved['events']:
        raise ValueError('Recorded-only proof differs')
    measurement = report['measurements']['pedestrian_entry_signal']['value']
    if report['case_id'] != case['case_id'] or measurement['entry_frame'] != 230 or \
            measurement['exit_frame'] != 291 or measurement['native_provenance'] or \
            measurement['legal_verdict'] is not None:
        raise ValueError('Diagnostic measurement identity or scope differs')
    for name, digest in report['measurements']['pedestrian_entry_signal']['sources'].items():
        if sha(bundle / 'sources' / name) != digest:
            raise ValueError('Retained source hash differs: ' + name)
    return config, measurement


def audit(root=HERE):
    manifest = read(root / 'v2-four-case-manifest.json')
    if manifest['runtime_manifest_sha256'] != sha(root.parents[1] / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError('Current runtime binding differs')
    cases = manifest['cases']
    if [c['case_id'].rsplit('__', 1)[-1] for c in cases] != list(EXPECTED):
        raise ValueError('Four exact case identities required')
    checked = [audit_case(c, root) for c in cases]
    configs, measurements = zip(*checked)
    for config in configs[1:]:
        for key in ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'cameras',
                    'traffic_head_id', 'pedestrian_head_id', 'required_atoms'):
            if config[key] != configs[0][key]:
                raise ValueError('Comparison fixed condition differs: ' + key)
    states = [m['pedestrian_signal_at_entry'] for m in measurements]
    if states != ['walk', 'dont_walk', 'walk', 'dont_walk']:
        raise ValueError('Declared pedestrian indication contrast absent')
    for left, right in ((0, 1), (2, 3)):
        for key in ('entry_frame', 'exit_frame', 'circular_green_at_entry', 'crosswalk_id'):
            if measurements[left][key] != measurements[right][key]:
                raise ValueError('Comparison measured condition differs: ' + key)
        if measurements[left]['deferred_to_484b_283_observed'] or \
                not measurements[right]['deferred_to_484b_283_observed']:
            raise ValueError('Deferral contrast absent')
    return {'format': 'c111331-four-case-diagnostic-audit-v1',
            'case_ids': [c['case_id'] for c in cases],
            'comparisons': ['witness_comparison', 'exception_1_comparison'],
            'current_runtime_sha256': manifest['runtime_manifest_sha256'],
            'public_compatibility_passed': 4, 'recorded_only_passed': 4,
            'source_negative_passed': 4, 'native_executed': False,
            'actual_pixels_reviewed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
