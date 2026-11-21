"""Build newly laid exact bundles with retained-source analysis/finalization."""
import json

from build_newly_laid_exact import (ASSIGNMENT, CASES, FALLBACKS, KNOBS,
                                    NATIVE, PACKAGE, build, sha, source_file)


def build_finalized(case, candidate='primary'):
    bundle = build(case, candidate)
    bundle['files'][-1:-1] = [
        source_file('native/' + name, NATIVE / name)
        for name in ('newly_laid_analyze.py', 'newly_laid_finalize.py')]
    bundle['status'] = 'draft_exact_newly_laid_source_finalization'
    bundle['mechanisms']['source_analysis'] = 'native/newly_laid_analyze.py'
    bundle['mechanisms']['finalization'] = 'native/newly_laid_finalize.py'
    bundle['measurement_procedure'] = {
        'entrypoint': 'native/newly_laid_finalize.py',
        'output_schema': 'c183370-newly-laid-diagnostic-finalization-v1'}
    return bundle


def write():
    cases = []
    for case in CASES:
        variants = {}
        for candidate in KNOBS:
            folder = PACKAGE / 'draft-newly-laid-finalized-candidates' / case / candidate
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'construction.json'
            if path.exists():
                raise ValueError('Retain previous newly laid finalizer construction')
            path.write_text(json.dumps(build_finalized(case, candidate),
                                       indent=2, sort_keys=True) + '\n')
            variants[candidate] = {
                'construction': str(path.relative_to(PACKAGE)),
                'construction_sha256': sha(path)}
        cases.append({
            'case_id': ASSIGNMENT + '__' + case, 'kind': 'delivery',
            **variants['primary'],
            'measurement_contract': 'newly-laid-measurement-contracts/' + case + '.json',
            'fixture_recipe': 'work/' + ASSIGNMENT +
                              '/newly-laid-diagnostics/' + case + '/primary-recipe.json',
            'measurement_procedure': {
                'entrypoint': 'native/newly_laid_finalize.py',
                'output_schema': 'c183370-newly-laid-diagnostic-finalization-v1'},
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Native body tracking and original warning/surface pixels remain unverified'},
            'candidates': [dict(id=name, **variants[name], **FALLBACKS[name])
                           for name in FALLBACKS],
            'candidate_offline_status': 'pending',
            'finalizer_status': 'source_derived_cpu_test_pending',
        })
    runtime = PACKAGE.parents[1] / 'runtime/pipeline/SOURCE-MANIFEST.json'
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': ASSIGNMENT,
        'status': 'draft_newly_laid_source_finalization_not_delivery_ready',
        'runtime_manifest_sha256': sha(runtime),
        'cases': cases}
    path = PACKAGE / 'draft-newly-laid-finalized-manifest.json'
    if path.exists():
        raise ValueError('Retain previous newly laid finalized manifest')
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return path


if __name__ == '__main__':
    print(write())
