"""Reject saved physical conclusions when selected Native body rows are missing."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    results = []
    manifest=read(HERE/'execution-manifest.json')
    selected={entry['case_id'].rsplit('__',1)[-1]:entry
              for entry in manifest['cases']}
    for suffix in ('reference', 'contrast'):
        attempt = ROOT/'.runtime-work'/f'c10014-update024-{suffix}-primary-missing-samples'
        saved = ROOT/'.runtime-work'/f'c10014-update024-{suffix}-primary-missing-saved/v0001'
        if (attempt/'native_samples.jsonl').exists():
            raise ValueError('Negative still has original body rows')
        processing = read(saved/'processing.json')
        result_path = Path(processing['result'])
        result = read(result_path)
        if (processing['passed'] is not True or processing['missing_evidence'] is not True or
                processing['case_id'] != HERE.name+'__'+suffix or
                processing['native_revision']['construction_sha256'] !=
                    selected[suffix]['construction_sha256'] or
                'native_samples.jsonl' in processing['original_source_hashes'] or
                result['provenance_kind'] != 'synthetic_fixture' or
                result.get('diagnostic_fixture') is not True):
            raise ValueError('Pinned missing-source scenario did not run as expected')
        checks = result['physical_checks']
        unsafe = [name for name in ('setup', 'target', 'maneuver', 'attempt')
                  if checks[name]['status'] != 'unverified']
        if result['realized_observables']:
            unsafe.append('realized_observables')
        if not unsafe:
            raise ValueError('Expected pinned fallback defect was not reproduced; review this audit')
        results.append({'case_id': processing['case_id'],
            'missing_native_samples': True, 'saved_processing_sha256': sha(saved/'processing.json'),
            'result_sha256': sha(result_path),
            'command_log_sha256': sha(HERE/f'update024-{suffix}-primary-missing-source.log'),
            'non_unverified_physical_fields': unsafe,
            'independent_acceptance': 'rejected',
            'reason': 'Missing required Native body rows cannot support a physical outcome from synthetic trace alone'})
    report = {'format': 'c10014-selected-missing-source-independent-audit',
              'manifest_sha256':sha(HERE/'execution-manifest.json'),
              'staged_manifest_sha256':sha(HERE/'execution-manifest-staged-update021.json'),
              'results': results, 'all_rejected': True,
              'scope': 'synthetic negative diagnostic; no Native original or legal acceptance'}
    (HERE/'update024-missing-source-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'unsafe_missing_source_results_rejected': len(results)}))


if __name__ == '__main__':
    audit()
