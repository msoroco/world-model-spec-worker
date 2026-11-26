"""Exercise exact exception-source isolation with synthetic diagnostic packets."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from runner import load_context

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent
FIELDS = {'exception_1': 'traffic_conflict',
          'exception_2': 'law_compliance',
          'exception_3': 'officer_direction',
          'exception_4': 'device_direction'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    scratch = Path(os.environ['TMPDIR']).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Scratch must be under .runtime-work')
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    results = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='context-') as temp:
        path = Path(temp) / 'context.json'
        for case in plan['cases']:
            case_id = case['case_id']
            suffix = case_id.rsplit('__', 1)[-1]
            record = {'case_id': case_id, 'source_kind': 'synthetic_cpu',
                      'activity': ('stop' if suffix.startswith('stop_') else
                                   'stand' if suffix.startswith('stand_') else 'park'),
                      **{key: False for key in FIELDS.values()}, 'sources': {}}
            if suffix.startswith('exception_'):
                field = FIELDS[suffix.rsplit('_', 1)[0]]
                record[field] = suffix.endswith('_2')
            else:
                field = 'traffic_conflict'
            path.write_text(json.dumps(record))
            accepted, source_sha = load_context(path, case_id)
            assert accepted == record and source_sha == sha(path)
            record[field] = not record[field]
            path.write_text(json.dumps(record))
            try:
                load_context(path, case_id)
            except ValueError:
                rejected = True
            else:
                rejected = False
            assert rejected
            record[field] = not record[field]
            record['activity'] = 'stand' if record['activity'] != 'stand' else 'stop'
            path.write_text(json.dumps(record))
            try:
                load_context(path, case_id)
            except ValueError:
                activity_rejected = True
            else:
                activity_rejected = False
            assert activity_rejected
            results.append({'case_id': case_id, 'positive_passed': True,
                            'source_mutation_rejected': True,
                            'activity_mutation_rejected': True})
        record = {'case_id': plan['cases'][0]['case_id'],
                  'source_kind': 'reviewed_authority_context',
                  'activity': 'park',
                  **{key: False for key in FIELDS.values()}, 'sources': {}}
        path.write_text(json.dumps(record))
        try:
            load_context(path, record['case_id'])
        except ValueError:
            missing_citation_rejected = True
        else:
            missing_citation_rejected = False
        assert missing_citation_rejected
        citation = Path(temp) / 'authority.txt'
        citation.write_text('Synthetic CPU authority text; not a legal source.\n')
        record['sources'] = {'authority': {'citation': 'Synthetic CPU source',
                                           'path': 'authority.txt', 'sha256': sha(citation)}}
        path.write_text(json.dumps(record))
        accepted, _ = load_context(path, record['case_id'])
        assert accepted == record
        citation.write_text('Tampered synthetic source.\n')
        try:
            load_context(path, record['case_id'])
        except ValueError as error:
            hash_mutation_rejected = 'hash differs' in str(error)
        else:
            hash_mutation_rejected = False
        assert hash_mutation_rejected
    proof = {'format': 'c229397-exception-source-isolation-v1',
             'runner_sha256': sha(ROOT / 'runner.py'),
             'case_plan_sha256': sha(PACKAGE / 'case-plan.json'),
             'cases': results, 'missing_citation_rejected': True,
             'reviewed_source_hash_mutation_rejected': True,
             'source_kind': 'synthetic_cpu',
             'original_native_observed': False,
             'legal_acceptance_claimed': False}
    (ROOT / 'source-context-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'passed': True}))


if __name__ == '__main__':
    main()
