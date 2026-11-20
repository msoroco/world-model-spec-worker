"""Independently audit three rebuilt same-cell diagnostic primary chains."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHORTS = ('barrier_crossing', 'warning_sign_crossing',
          'employee_exception_employee_crossing')
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
            'selected_measurements', 'negative_case_source'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'draft-combined-capture-manifest.json'
    manifest, digest = read(manifest_path), sha(manifest_path)
    assert len(manifest['cases']) == 10
    rows = []
    for short in SHORTS:
        case = HERE.name + '__' + short
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        construction = read(HERE / entry['construction'])
        assert sha(HERE / entry['construction']) == entry['construction_sha256']
        for module in ('statutory_variants.py', 'variant_capture.py',
                       'variant_analyze.py'):
            embedded = next(item['content'] for item in construction['files']
                            if item['path'] == 'native/' + module)
            assert embedded == (HERE / 'native' / module).read_text()
        offline = read(ROOT / '.runtime-work/c183370-update125-combined-offline-matrix'
                       / short / 'primary/candidate-selection.json')
        base = ROOT / '.runtime-work' / ('c183370-update125-combined-' + short + '-primary')
        compat, source, saved = (Path(str(base) + suffix) for suffix in
                                 ('-compat', '-source', '-saved/v0001'))
        selection = read(compat / 'candidate-selection.json')
        proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
        report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
        assert all(row['case_id'] == case and row['candidate_id'] == 'primary'
                   for row in (offline, selection, proof, processed))
        assert offline['manifest_sha256'] == selection['manifest_sha256'] == \
            read(source / 'candidate-selection.json')['manifest_sha256'] == digest
        assert offline['construction_sha256'] == selection['construction_sha256'] == \
            proof['construction_sha256'] == processed['analysis_revision']['construction_sha256'] == \
            entry['construction_sha256']
        assert proof['passed'] is True and REQUIRED <= set(proof['checks'])
        assert proof['negative_removed'] == 'live-readback.json'
        assert 'Missing required source: live-readback.json' in \
            (compat / 'negative-analysis.log').read_text()
        assert processed['passed'] is True and processed['recorded_only'] is True
        assert processed['originals_preserved'] is True and processed['missing_evidence'] is False
        assert processed['timestamp_joins']['passed'] is True
        assert processed['timestamp_joins']['frames'] == 600
        assert processed['final_video_checks']['passed'] is True
        assert report['analysis_complete'] is True and report['diagnostic_fixture'] is True
        assert report['physical_acceptance_claimed'] is False
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        measure = report['measurements']['surveyed_pavement_contact']
        assert measure['value']['measured_contact'] is True
        assert len(measure['value']['contact_frames']) == 300
        for name, source_hash in measure['sources'].items():
            assert sha(source / name) == processed['original_source_hashes'][name] == source_hash
        rows.append({'case_id': case, 'construction_sha256': entry['construction_sha256'],
                     'offline_sha256': sha(ROOT / '.runtime-work/c183370-update125-combined-offline-matrix'
                                           / short / 'primary/candidate-selection.json'),
                     'compatibility_sha256': sha(compat / 'compatibility.json'),
                     'saved_sha256': sha(saved / 'processing.json')})
    return {'format': 'c183370-same-cell-primary-diagnostic-audit-v1',
            'manifest_sha256': digest, 'primary_count': len(rows),
            'passed': True, 'diagnostic_only': True,
            'original_native_or_legal_acceptance_claimed': False, 'rows': rows}


if __name__ == '__main__':
    target = HERE / 'update125-same-cell-primary-audit.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
