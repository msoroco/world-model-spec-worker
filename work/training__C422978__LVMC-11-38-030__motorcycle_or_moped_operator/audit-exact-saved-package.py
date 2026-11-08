"""Independent audit of eight current bundled C422978 saved-meter executions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(HERE / 'draft-execution-manifest.json')
    proof = read(HERE / 'exact-saved-package-proof.json')
    assert proof['manifest_sha256'] == sha(HERE / 'draft-execution-manifest.json')
    assert len(proof['results']) == 8
    assert not proof['original_native_or_delivery_acceptance_claimed']
    audited = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = entry if candidate == 'primary' else next(
                r for r in entry['candidates'] if r['id'] == candidate)
            construction_path = HERE / ref['construction']
            assert ref['construction_sha256'] == sha(construction_path)
            files = {f['path']: f['content'] for f in read(construction_path)['files']}
            assert files['measure_saved.py'] == (HERE / 'native/measure_saved.py').read_text()
            proof_row = next(r for r in proof['results'] if r['case_id'] == entry['case_id']
                             and r['candidate_id'] == candidate)
            assert proof_row['construction_sha256'] == ref['construction_sha256']
            folder = HERE / 'draft-candidates' / case / candidate
            positive = folder / 'saved-package-positive.json'
            negative = folder / 'saved-package-negative.log'
            assert proof_row['positive_sha256'] == sha(positive)
            assert proof_row['negative_log_sha256'] == sha(negative)
            assert 'Missing required source: native-observed.jsonl' in negative.read_text()
            value = read(positive)
            original = read(HERE / 'native/saved-fixtures' / case / candidate / 'analysis-report.json')
            assert value == original
            assert value['frames'] == 480 and value['source_kind'] == 'synthetic_cpu'
            assert bool(value['moving_sidewalk_overlap_frames']) == (case == 'witness_2')
            assert not value['city_sidewalk_verified'] and value['legal_verdict'] is None
            for name, checksum in value['source_hashes'].items():
                assert checksum == sha(HERE / 'native/saved-fixtures' / case / candidate / name)
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'positive_sha256': proof_row['positive_sha256']})
    output = {'format': 'c422978-independent-exact-saved-package-audit-v1',
              'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
              'proof_sha256': sha(HERE / 'exact-saved-package-proof.json'),
              'audited': audited, 'original_native_or_delivery_acceptance_claimed': False}
    (HERE / 'exact-saved-package-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited'])}))
