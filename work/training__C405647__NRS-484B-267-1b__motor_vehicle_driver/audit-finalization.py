"""Independent receipt audit for exact unselected 1(b) finalizers."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = FOLDER / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads((FOLDER / 'exact-finalization-proof.json').read_text())
    assert proof['manifest_sha256'] == sha(manifest_path)
    assert proof['core_video_compatibility_claimed'] is False
    rows = {(r['case_id'], r['candidate_id']): r for r in proof['results']}
    assert len(rows) == 8
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = rows[(entry['case_id'], candidate)]
            selected = entry if candidate == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate)
            assert row['construction_sha256'] == selected['construction_sha256']
            folder = FOLDER / 'draft-candidates' / case / candidate
            report_path = folder / 'finalization-analysis.json'
            result_path = folder / 'finalization-result.json'
            negative_path = folder / 'finalization-negative.log'
            assert row['analysis_sha256'] == sha(report_path)
            assert row['result_sha256'] == sha(result_path)
            assert row['negative_log_sha256'] == sha(negative_path)
            assert 'Saved actor/trace/video frame join differs' in negative_path.read_text()
            report = json.loads(report_path.read_text())
            result = json.loads(result_path.read_text())
            assert report['case_id'] == result['case_id'] == entry['case_id']
            assert report['draft_only'] is True and report['legal_verdict_claimed'] is False
            measurement = report['measurements']['right_edge_geometry']['value']
            assert measurement['frames'] == row['frame_count'] == 480
            assert measurement['source_kind'] == 'synthetic_cpu'
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert measurement['edge_before_catchup'] == (case == 'reference')
            assert len(result['recording_evidence']) == row['recording_channels'] == 3
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['target_checks'][0]['matched'] is True
            assert result['target_checks'][0]['physical_cause_confirmed'] is False
            assert measurement['vehicle_authority_or_lamps_qualified'] is False
            assert measurement['legal_immediacy_or_edge_verdict'] is None
    result = {'passed': True, 'exact_finalizer_positives': 8,
              'changed_join_negatives': 8,
              'core_video_or_physical_acceptance_claimed': False}
    (FOLDER / 'exact-finalization-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
