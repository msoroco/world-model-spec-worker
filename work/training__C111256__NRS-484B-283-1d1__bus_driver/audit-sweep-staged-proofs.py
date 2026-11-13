"""Independently cross-check the unselected sweep's current CPU proof chains."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest, offline, compatibility, saved, construction):
    if manifest['status'] != 'unselected_cpu_construction' or len(manifest['cases']) != 4:
        raise ValueError('Sweep selection or coverage differs')
    manifest_hash = sha(HERE / 'sweep-execution-candidate.json')
    if any(matrix.get(key) != manifest_hash for matrix, key in (
            (offline, 'manifest_sha256'), (compatibility, 'staged_manifest_sha256'),
            (saved, 'staged_manifest_sha256'), (construction, 'candidate_manifest_sha256'))):
        raise ValueError('Stale staged manifest binding')
    if compatibility['status'] != 'complete_diagnostic' or saved['status'] != 'complete_diagnostic':
        raise ValueError('Incomplete staged proof matrix')
    if (offline['offline_passed'] != 16 or construction['offline_bundles_passed'] != 16
            or construction['setpoint_mutations_rejected'] != 16):
        raise ValueError('Construction or offline proof incomplete')
    expected = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in [{'id': 'primary', 'construction': entry['construction'],
                           'construction_sha256': entry['construction_sha256']}, *entry['candidates']]:
            key = (entry['case_id'], candidate['id'])
            if key in expected or sha(HERE / candidate['construction']) != candidate['construction_sha256']:
                raise ValueError('Duplicate or changed construction')
            expected[key] = (suffix, candidate['construction_sha256'])
    if len(expected) != 16:
        raise ValueError('Wrong sweep case/candidate count')

    def index(rows, label):
        indexed = {(r['case_id'], r['candidate_id']): r for r in rows}
        if len(indexed) != len(rows) or set(indexed) != set(expected):
            raise ValueError('Missing or duplicate ' + label)
        return indexed

    off = index(offline['rows'], 'offline')
    pos = index(compatibility['rows'], 'compatibility')
    proc = index(saved['rows'], 'saved processing')
    built = {(r['case_id'], r['candidate']): r for r in construction['bundles']}
    if set(built) != set(expected):
        raise ValueError('Missing construction bundle')
    for key, (suffix, construction_hash) in expected.items():
        if any(row['construction_sha256'] != construction_hash for row in
               (off[key], pos[key], proc[key], built[key])):
            raise ValueError('Candidate source hash differs')
        offline_log = HERE / off[key]['log']
        if sha(offline_log) != off[key]['log_sha256'] or off[key]['exit_code'] != 0:
            raise ValueError('Offline log changed')
        positive = pos[key]
        receipt_path = HERE / positive['receipt']
        receipt = read(receipt_path)
        if (sha(receipt_path) != positive['receipt_sha256'] or
                receipt['passed'] is not True or receipt['scope'] != 'diagnostic software compatibility only' or
                receipt['case_id'] != key[0] or receipt['candidate_id'] != key[1] or
                receipt['construction_sha256'] != construction_hash or
                receipt['fixture_recipe_sha256'] != sha(HERE / 'update028-sweep-recipe.json') or
                receipt['negative_error_contains'] != 'Missing required source: road_geometry.json'):
            raise ValueError('Compatibility receipt changed or claims wrong scope')
        for name, hash_key in (('positive-analysis.log', 'positive_log_sha256'),
                               ('negative-analysis.log', 'negative_log_sha256')):
            if sha(receipt_path.parent / name) != positive[hash_key]:
                raise ValueError('Compatibility log changed')
        processed = proc[key]
        processing_path = HERE / processed['receipt']
        processing = read(processing_path)
        if (sha(processing_path) != processed['receipt_sha256'] or
                processing['passed'] is not True or processing['recorded_only'] is not True or
                processing['case_id'] != key[0] or processing['candidate_id'] != key[1] or
                processing['native_revision']['construction_sha256'] != construction_hash or
                processing['physical_acceptance_claimed'] is not False or
                processing['legal_acceptance_claimed'] is not False):
            raise ValueError('Saved-processing receipt changed or claims acceptance')
        if sha(processing_path.parent / 'analysis.log') != processed['analysis_log_sha256']:
            raise ValueError('Saved analysis log changed')
    if (compatibility['original_recordings_accepted'] != 0 or
            saved['original_recordings_accepted'] != 0 or
            construction['original_recordings_accepted'] != 0):
        raise ValueError('Diagnostic matrix claimed original acceptance')
    return len(expected)


def main():
    names = ('sweep-execution-candidate.json', 'update029-sweep-runtime-offline-matrix.json',
             'update028-sweep-staged-compat-matrix.json', 'update028-sweep-staged-process-matrix.json',
             'update029-sweep-construction-proof.json')
    docs = [read(HERE / name) for name in names]
    count = check(*docs)
    negatives = 0
    for mutation in ('missing_saved', 'stale_source', 'claimed_original'):
        altered = copy.deepcopy(docs)
        if mutation == 'missing_saved':
            altered[3]['rows'].pop()
        elif mutation == 'stale_source':
            altered[0]['cases'][0]['construction_sha256'] = '0' * 64
        else:
            altered[3]['original_recordings_accepted'] = 1
        try:
            check(*altered)
        except ValueError:
            negatives += 1
        else:
            raise ValueError('Damaged proof matrix was accepted: ' + mutation)
    result = {'format': 'c111256-unselected-sweep-proof-audit-v1',
              'staged_manifest_sha256': sha(HERE / names[0]),
              'proof_sources': {name: sha(HERE / name) for name in names[1:]},
              'candidate_chains_checked': count, 'mutations_rejected': negatives,
              'selected': False, 'original_recordings_accepted': 0}
    path = HERE / 'update029-sweep-proof-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'candidate_chains_checked': count, 'mutations_rejected': negatives,
                      'proof_sha256': sha(path), 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
