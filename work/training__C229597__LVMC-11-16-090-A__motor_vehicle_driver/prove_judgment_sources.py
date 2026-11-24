"""Positive unknown and negative-source checks for both selected cases."""
import hashlib
import json
from pathlib import Path

from audit_judgment_sources import audit
from prove_selected_review_sources import SCRATCH, main as prepare_sources

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(attempt, label, path, change):
    original = path.read_bytes()
    path.write_bytes(change(original))
    try:
        audit(attempt)
    except (ValueError, FileNotFoundError, KeyError) as error:
        result = {'name': label, 'rejected': True, 'error': str(error)}
    else:
        raise AssertionError(label + ' accepted')
    finally:
        path.write_bytes(original)
    return result


def alter_context(field, value):
    def change(raw):
        record = json.loads(raw)
        root = next(iter(record))
        record[root][field] = value
        return json.dumps(record).encode()
    return change


def one(case):
    attempt = SCRATCH / case
    positive = audit(attempt)
    if [row['status'] for row in positive['judgments']] != ['unknown', 'unknown']:
        raise AssertionError('Synthetic judgments must remain unknown')
    negatives = [
        reject(attempt, 'missing_exhibition_context',
               attempt / 'channels/exhibition_episode_context.json', lambda raw: b'{}'),
        reject(attempt, 'missing_highway_survey',
               attempt / 'channels/original_highway_survey.json', lambda raw: b'{}'),
        reject(attempt, 'forged_exhibition',
               attempt / 'channels/exhibition_episode_context.json',
               alter_context('exhibition_review', 'exhibition')),
        reject(attempt, 'forged_highway',
               attempt / 'channels/original_highway_survey.json',
               alter_context('highway_classification', 'highway')),
        reject(attempt, 'ambiguous_highway',
               attempt / 'channels/original_highway_survey.json',
               alter_context('highway_classification', 'ambiguous')),
        reject(attempt, 'forged_jurisdiction',
               attempt / 'channels/original_highway_survey.json',
               alter_context('jurisdiction_source', 'synthetic-road-name')),
        reject(attempt, 'changed_ego_motion', attempt / 'trace.jsonl',
               lambda raw: raw + b'\n'),
    ]
    if audit(attempt) != positive:
        raise AssertionError('Restored judgment sources no longer pass')
    return {'case_id': positive['case_id'], 'positive': positive,
            'negative_cases': negatives}


def main():
    prepare_sources()
    cases = [one(name) for name in ('reference', 'contrast')]
    proof = {
        'format': 'c229597-judgment-source-proof-v1',
        'law_id': 'LVMC-11-16-090-A',
        'auditor_sha256': sha(HERE / 'audit_judgment_sources.py'),
        'integrity_auditor_sha256': sha(HERE / 'audit_saved_review_sources.py'),
        'source_builder_sha256': sha(HERE / 'prove_selected_review_sources.py'),
        'selected_cases': cases,
        'all_judgments_unknown': True, 'synthetic_fixture': True,
        'native_executed': False, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }
    path = HERE / 'judgment-source-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': len(cases),
                      'negative_rejections': sum(len(x['negative_cases']) for x in cases),
                      'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
