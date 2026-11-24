"""Bind all 56 fresh current-runner short public proofs into one draft."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SOURCE = WORK / 'current-runtime-runner-reference-bound-manifest.json'
INDEX = WORK / 'current-runtime-runner-short-public-index.json'
TARGET = WORK / 'current-runtime-runner-short-bound-manifest.json'
AUDIT = WORK / 'current-runtime-runner-short-public-binding.json'
TEMP = REPO / '.runtime-work/owner150142/short-public-binding-tmp'
VARIANTS = ('primary', 'fallback1', 'fallback2', 'fallback3')
CHECKS = {'selected_measurements', 'negative_case_source',
          'lean_decoder', 'final_decode'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    TEMP.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=TEMP,
                                     delete=False) as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    os.replace(temporary, path)


def run():
    manifest = json.loads(SOURCE.read_text())
    index = json.loads(INDEX.read_text())
    rows = index['rows']
    if (index['completed'] != 52 or index['expected'] != 52 or
            len(rows) != 52 or index['source_manifest_sha256'] !=
            sha(WORK / 'current-runtime-runner-offline-bound-manifest.json')):
        raise ValueError('All 52 remaining current-runner public proofs are required')
    expected = {(item['case_id'], candidate)
                for item in manifest['cases']
                if item['case_id'].split('__')[-1] in
                {row['case_id'].split('__')[-1] for row in rows}
                for candidate in VARIANTS}
    seen = {(row['case_id'], row['candidate_id']) for row in rows}
    if len(seen) != 52 or seen != expected:
        raise ValueError('Short public index has missing or duplicate candidate identity')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        if case_id.endswith('__reference') or (case_id, 'primary') not in seen:
            continue
        suffix = case_id.removeprefix(WORK.name + '__')
        fields = {'primary': entry,
                  **{candidate['id']: candidate for candidate in entry['candidates']}}
        for candidate in VARIANTS:
            field = fields[candidate]
            portable = WORK / 'current-runtime-runner-public' / suffix / candidate
            receipt = portable / 'compatibility.json'
            positive = portable / 'positive-analysis.log'
            negative = portable / 'negative-analysis.log'
            if not all(path.is_file() for path in (receipt, positive, negative)):
                raise ValueError('Missing current-runner public receipt: ' + str(portable))
            proof = json.loads(receipt.read_text())
            if (proof.get('case_id') != case_id or
                    proof.get('candidate_id') != candidate or
                    proof.get('construction_sha256') != field['construction_sha256'] or
                    proof.get('runtime_manifest_sha256') !=
                    manifest['runtime_manifest_sha256'] or
                    proof.get('passed') is not True or
                    not CHECKS <= set(proof.get('checks', [])) or
                    proof.get('log_sha256') != sha(positive) or
                    proof.get('negative_log_sha256') != sha(negative) or
                    proof.get('negative_error_contains') not in negative.read_text()):
                raise ValueError('Fresh public proof does not bind ' + suffix + '/' + candidate)
            row = next(row for row in rows if row['case_id'] == case_id and
                       row['candidate_id'] == candidate)
            if (row['construction_sha256'] != field['construction_sha256'] or
                    row['receipt_sha256'] != sha(receipt) or
                    row['log_sha256'] != sha(positive) or
                    row['negative_log_sha256'] != sha(negative)):
                raise ValueError('Public index hash changed: ' + suffix + '/' + candidate)
            field['compatibility'] = {
                'receipt': str(receipt.relative_to(WORK)),
                'sha256': sha(receipt),
                'log': str(positive.relative_to(WORK)),
                'negative_log': str(negative.relative_to(WORK)),
            }
            field['negative'] = {'log': str(negative.relative_to(WORK))}
    manifest['status'] = 'draft_current_runner_short_public_bound'
    manifest['delivery_ready'] = False
    save_json(TARGET, manifest)
    audit = {
        'format': 'c150142-current-runner-short-public-binding-v1',
        'passed': True, 'delivery_ready': False,
        'case_count': 14, 'candidate_count': 56,
        'source_manifest_sha256': sha(SOURCE),
        'short_index_sha256': sha(INDEX),
        'bound_manifest_sha256': sha(TARGET),
        'reference_candidates': 4, 'other_short_candidates': 52,
    }
    save_json(AUDIT, audit)
    return audit


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
