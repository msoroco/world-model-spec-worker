"""Independently audit retained exact-bundle saved packet probes."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    proof = json.loads((FOLDER / 'exact-saved-package-proof.json').read_text())
    manifest_path = FOLDER / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert proof['draft_manifest_sha256'] == sha(manifest_path)
    assert not proof['physical_or_legal_acceptance_claimed']
    assert not proof['full_core_video_compatibility_claimed']
    expected = {(entry['case_id'], candidate) for entry in manifest['cases']
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    rows = {(row['case_id'], row['candidate_id']): row for row in proof['results']}
    assert len(rows) == len(expected) == 8 and set(rows) == expected
    audited = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = rows[(entry['case_id'], candidate)]
            selected = entry if candidate == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate)
            construction_path = FOLDER / selected['construction']
            construction = json.loads(construction_path.read_text())
            processor = next(x['content'] for x in construction['files']
                             if x['path'] == 'measure_saved.py')
            assert sha(construction_path) == selected['construction_sha256'] == row['construction_sha256']
            assert hashlib.sha256(processor.encode()).hexdigest() == row['bundle_measure_saved_sha256']
            positive_path = FOLDER / row['positive_log']
            negative_path = FOLDER / row['negative_log']
            assert sha(positive_path) == row['positive_log_sha256']
            assert sha(negative_path) == row['negative_log_sha256']
            assert row['positive_exit_code'] == 0 and row['missing_source_exit_code'] != 0
            assert row['missing_source_error'] in negative_path.read_text()
            measured = json.loads(positive_path.read_text())
            assert measured['scope_sha256'] == row['scope_sha256']
            assert measured['actor_frames_sha256'] == row['actor_frames_sha256']
            assert measured['first_edge_target_frame'] == row['edge_frame']
            assert measured['approach_catchup_frame'] == row['catchup_frame']
            assert measured['frames'] == 480 and measured['source_kind'] == 'synthetic_cpu'
            assert measured['edge_before_catchup'] == (suffix == 'reference')
            assert measured['vehicle_authority_or_lamps_qualified'] is False
            assert measured['legal_immediacy_or_edge_verdict'] is None
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'positive_log_sha256': row['positive_log_sha256'],
                            'negative_log_sha256': row['negative_log_sha256']})
    result = {'passed': True, 'exact_bundle_count': len(audited),
              'positive_count': len(audited), 'negative_count': len(audited),
              'core_video_or_physical_acceptance_claimed': False, 'rows': audited}
    (FOLDER / 'exact-saved-package-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
