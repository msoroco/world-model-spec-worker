"""Audit both current barrier CPU chains without asserting physical success."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = PACKAGE / 'draft-barrier-capture-manifest.json'
    manifest = read(manifest_path)
    rows = []
    expected_checks = {'actual_analysis', 'native_validation',
                       'mandatory_observations', 'lean_decoder', 'render',
                       'final_decode', 'acquisition_unchanged',
                       'derived_outputs_rebuilt', 'four_camera_sources',
                       'selected_measurements', 'negative_case_source'}
    for route, count in (('crossing', 300), ('avoidance', 0)):
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('barrier_' + route))
        base = REPO / '.runtime-work' / ('c183370-update111-barrier-' + route)
        compat = Path(str(base) + '-compat')
        saved = Path(str(base) + ('-saved-clean' if route == 'crossing' else '-saved')) / 'v0001'
        attempt = Path(str(base) + '-source')
        proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
        result, report = read(saved / 'analysis/result.json'), read(saved / 'analysis/analysis-report.json')
        assert proof['passed'] is True and expected_checks <= set(proof['checks'])
        assert proof['case_id'] == entry['case_id'] and proof['candidate_id'] == 'primary'
        assert proof['construction_sha256'] == entry['construction_sha256']
        assert proof['negative_removed'] == 'live-readback.json'
        assert 'Missing required source: live-readback.json' in (compat / 'negative-analysis.log').read_text()
        assert processed['passed'] is True and processed['missing_evidence'] is False
        assert processed['originals_preserved'] is True
        assert processed['timestamp_joins']['passed'] is True
        assert processed['timestamp_joins']['frames'] == 600
        assert processed['final_video_checks']['passed'] is True
        assert processed['analysis_revision']['construction_sha256'] == entry['construction_sha256']
        assert report['analysis_complete'] is True and report['diagnostic_fixture'] is True
        assert result['diagnostic_fixture'] is True and result['accepted'] is False
        assert result['legal_verdict_claimed'] is False
        assert report['physical_acceptance_claimed'] is False
        measure = report['measurements']['surveyed_pavement_contact']['value']
        assert measure['measured_contact'] == (route == 'crossing')
        assert measure['requested_contact_matched'] is True
        assert len(measure['contact_frames']) == count
        for name, checksum in report['measurements']['surveyed_pavement_contact']['sources'].items():
            assert processed['original_source_hashes'][name] == checksum
            assert sha(attempt / name) == checksum
        assert not (attempt / 'recorded-context.json').exists()
        rows.append({'case_id': entry['case_id'], 'candidate': 'primary',
                     'construction_sha256': entry['construction_sha256'],
                     'offline_log_sha256': sha(PACKAGE / f'update111-barrier-{route}-offline.log'),
                     'compatibility_log_sha256': sha(PACKAGE / f'update111-barrier-{route}-compat.log'),
                     'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                     'saved_log_sha256': sha(PACKAGE / ('update111-barrier-crossing-saved-clean.log' if route == 'crossing' else
                                                        'update111-barrier-avoidance-saved.log')),
                     'saved_receipt_sha256': sha(saved / 'processing.json'),
                     'contact_frames': count, 'source_frames': 600,
                     'originals_preserved': True, 'physical_acceptance_claimed': False})
    return {'format': 'c183370-barrier-diagnostic-primary-matrix-v1',
            'scope': 'synthetic diagnostic software compatibility only',
            'manifest_sha256': sha(manifest_path),
            'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
            'both_passed': True, 'native_capture_claimed': False,
            'physical_acceptance_claimed': False, 'cases': rows}


if __name__ == '__main__':
    output = PACKAGE / 'update111-barrier-primary-diagnostic-matrix.json'
    output.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
