"""Independently audit eight current same-cell barrier diagnostic chains."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
ROUTES = ('crossing', 'avoidance')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = PACKAGE / 'draft-combined-capture-manifest.json'
    manifest = read(manifest_path)
    digest = sha(manifest_path)
    offline = read(PACKAGE / 'update125-combined-offline-matrix.json')
    assert offline['manifest_sha256'] == digest and offline['passed'] == 40
    required = {'actual_analysis', 'native_validation', 'mandatory_observations',
                'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
                'selected_measurements', 'negative_case_source'}
    rows = []
    for route in ROUTES:
        case = PACKAGE.name + '__barrier_' + route
        entry = next(item for item in manifest['cases'] if item['case_id'] == case)
        configs = set()
        for candidate in CANDIDATES:
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            construction = read(PACKAGE / selected['construction'])
            configs.add(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
            base = REPO / '.runtime-work' / (
                'c183370-update125-combined-barrier_' + route + '-' + candidate)
            compat, source, saved = (Path(str(base) + suffix) for suffix in
                                     ('-compat', '-source', '-saved/v0001'))
            selection = read(compat / 'candidate-selection.json')
            proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
            report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
            assert selection['manifest_sha256'] == digest
            assert selection['case_id'] == case and selection['candidate_id'] == candidate
            assert selection['construction_sha256'] == selected['construction_sha256']
            assert proof['passed'] is True and required <= set(proof['checks'])
            assert proof['case_id'] == case and proof['candidate_id'] == candidate
            assert proof['construction_sha256'] == selected['construction_sha256']
            assert proof['negative_removed'] == 'live-readback.json'
            assert 'Missing required source: live-readback.json' in \
                (compat / 'negative-analysis.log').read_text()
            assert read(source / 'candidate-selection.json')['manifest_sha256'] == digest
            assert processed['passed'] is True and processed['recorded_only'] is True
            assert processed['originals_preserved'] is True and processed['missing_evidence'] is False
            assert processed['timestamp_joins']['passed'] is True
            assert processed['timestamp_joins']['frames'] == 600
            assert processed['final_video_checks']['passed'] is True
            assert processed['analysis_revision']['construction_sha256'] == selected['construction_sha256']
            assert report['analysis_complete'] is True and report['diagnostic_fixture'] is True
            assert report['physical_acceptance_claimed'] is False
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            measurement = report['measurements']['surveyed_pavement_contact']['value']
            assert measurement['measured_contact'] == (route == 'crossing')
            assert measurement['requested_contact_matched'] is True
            assert len(measurement['contact_frames']) == (300 if route == 'crossing' else 0)
            for name, source_hash in report['measurements']['surveyed_pavement_contact']['sources'].items():
                assert sha(source / name) == processed['original_source_hashes'][name] == source_hash
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                         'saved_receipt_sha256': sha(saved / 'processing.json'),
                         'contact_frames': len(measurement['contact_frames'])})
        assert len(configs) == 4
    return {'manifest_sha256': digest, 'candidate_count': len(rows),
            'all_passed': True, 'diagnostic_only': True,
            'physical_or_legal_acceptance_claimed': False, 'rows': rows}


if __name__ == '__main__':
    target = PACKAGE / 'update127-current-barrier-pair-audit.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_count': 8, 'all_passed': True,
                      'audit_sha256': sha(target)}, sort_keys=True))
