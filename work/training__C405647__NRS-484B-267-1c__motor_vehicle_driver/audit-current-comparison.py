"""Independently compare source-bound saved diagnostic branch pairs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = {e['case_id']: e for e in manifest['cases']}
    results = []
    for comparison in plan['comparisons']:
        case_a, case_b = comparison['case_ids']
        suffix_a, suffix_b = case_a.rsplit('__', 1)[-1], case_b.rsplit('__', 1)[-1]
        sources = []
        pair = []
        for case, suffix in ((case_a, suffix_a), (case_b, suffix_b)):
            source = HERE / 'current-fixture' / suffix / 'actor-frames.jsonl'
            scope_path = HERE / 'current-fixture' / suffix / 'context-scope.json'
            receipt_path = HERE / 'current-public' / (suffix + '-primary-compatibility.json')
            process_path = HERE / 'current-public' / (suffix + '-primary-processing.json')
            receipt, processing = json.loads(receipt_path.read_text()), json.loads(process_path.read_text())
            if (not receipt['passed'] or not processing['passed'] or
                receipt['construction_sha256'] != entries[case]['construction_sha256'] or
                processing['analysis_revision']['construction_sha256'] != entries[case]['construction_sha256'] or
                processing['original_source_hashes']['actor-frames.jsonl'] != sha(source)):
                raise ValueError('Exact source or construction changed: ' + case)
            pair.append((rows(source), json.loads(scope_path.read_text())))
            sources.append({'case_id': case, 'actor_frames_sha256': sha(source),
                            'context_sha256': sha(scope_path),
                            'compatibility_sha256': sha(receipt_path),
                            'processing_sha256': sha(process_path)})
        (a, scope_a), (b, scope_b) = pair
        if len(a) != 600 or len(b) != 600:
            raise ValueError('Missing 600-frame comparison')
        for i, (one, two) in enumerate(zip(a, b)):
            if (one['frame'], one['native_frame'], one['time_s']) != (two['frame'], two['native_frame'], two['time_s']) or one['approach'] != two['approach']:
                raise ValueError('Fixed approach or time differs at frame ' + str(i))
        variable = comparison['deliberate_differences'][0]
        if variable == 'officer_direction_applicability':
            if scope_a['officer_direction_request'] is not False or scope_b['officer_direction_request'] is not True or any(one['subject'] != two['subject'] for one, two in zip(a,b)):
                raise ValueError('Officer exception pair changes more than direction request')
        else:
            first_a = next(i for i,r in enumerate(a) if r['subject']['speed_mps'] > .05)
            first_b = next(i for i,r in enumerate(b) if r['subject']['speed_mps'] > .05)
            if not first_a > first_b or scope_a['approach_kind_request'] != scope_b['approach_kind_request'] or scope_a['officer_direction_request'] != scope_b['officer_direction_request']:
                raise ValueError('Wait pair release or fixed context differs')
        results.append({'comparison_id': comparison['comparison_id'], 'case_ids': comparison['case_ids'],
                        'frames_per_case': 600, 'fixed_approach_and_time_join': True,
                        'isolated_variable': variable, 'sources': sources,
                        'diagnostic_only': True, 'original_native_observed': False})
    out = HERE / 'current-public/comparison-audit.json'
    out.write_text(json.dumps({'format':'c405647-1c-current-comparison-audit',
                               'comparisons':results, 'physical_acceptance':False,
                               'legal_verdict':None}, indent=2) + '\n')
    print(json.dumps({'passed':True, 'comparisons':len(results), 'sha256':sha(out)}))

if __name__ == '__main__':
    main()
