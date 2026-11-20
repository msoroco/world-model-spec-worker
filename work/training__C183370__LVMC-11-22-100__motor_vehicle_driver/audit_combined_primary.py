"""Independently bind one combined-manifest barrier diagnostic proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__barrier_crossing'
BASE = ROOT / '.runtime-work/c183370-update115-combined-barrier-primary'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'draft-combined-capture-manifest.json'
    manifest = read(manifest_path)
    assert len(manifest['cases']) == 10
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    assert sha(HERE / entry['construction']) == entry['construction_sha256']
    offline = read(Path(str(BASE) + '-offline/candidate-selection.json'))
    compat_dir = Path(str(BASE) + '-compat')
    compat = read(compat_dir / 'compatibility.json')
    source_dir = Path(str(BASE) + '-source')
    selected = read(source_dir / 'candidate-selection.json')
    saved_dir = Path(str(BASE) + '-saved/v0001')
    saved = read(saved_dir / 'processing.json')
    report = read(saved_dir / 'analysis/analysis-report.json')
    result = read(saved_dir / 'analysis/result.json')
    required = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    assert all(row['case_id'] == CASE and row['candidate_id'] == 'primary'
               for row in (offline, compat, selected, saved))
    assert offline['manifest_sha256'] == selected['manifest_sha256'] == sha(manifest_path)
    assert offline['construction_sha256'] == selected['construction_sha256'] == \
        compat['construction_sha256'] == saved['analysis_revision']['construction_sha256'] == \
        entry['construction_sha256']
    assert compat['passed'] is True and required <= set(compat['checks'])
    assert compat['negative_removed'] == 'live-readback.json'
    assert 'Missing required source: live-readback.json' in \
        (compat_dir / 'negative-analysis.log').read_text()
    assert saved['passed'] is True and saved['recorded_only'] is True
    assert saved['originals_preserved'] is True and saved['missing_evidence'] is False
    assert saved['timestamp_joins']['passed'] is True and \
        saved['timestamp_joins']['frames'] == 600
    assert saved['final_video_checks']['passed'] is True
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert report['physical_acceptance_claimed'] is False
    assert report['measurements']['surveyed_pavement_contact']['value']['measured_contact'] is True
    for name, digest in report['measurements']['surveyed_pavement_contact']['sources'].items():
        assert sha(source_dir / name) == saved['original_source_hashes'][name] == digest
    return {'passed': True, 'case_id': CASE,
            'manifest_sha256': sha(manifest_path),
            'construction_sha256': entry['construction_sha256'],
            'compatibility_receipt_sha256': sha(compat_dir / 'compatibility.json'),
            'saved_receipt_sha256': sha(saved_dir / 'processing.json'),
            'source_frames': 600, 'diagnostic_only': True,
            'original_native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
