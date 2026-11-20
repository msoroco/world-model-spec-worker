"""Independently audit eight combined-manifest highway-closed-sign diagnostic chains."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = PACKAGE / 'draft-combined-capture-manifest.json'
    manifest, digest = read(manifest_path), sha(manifest_path)
    offline = read(PACKAGE / 'update115-combined-offline-matrix.json')
    assert offline['manifest_sha256'] == digest and offline['passed'] == 40
    rows = []
    for route, count in (('crossing', 300), ('avoidance', 0)):
        short = 'highway_closed_sign_' + route
        case = PACKAGE.name + '__' + short
        entry = next(item for item in manifest['cases'] if item['case_id'] == case)
        configs = set()
        for candidate in CANDIDATES:
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            construction = read(PACKAGE / selected['construction'])
            configs.add(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
            base = REPO / '.runtime-work' / (
                'c183370-update116-combined-' + short + '-' + candidate)
            compat, source, saved = (Path(str(base) + suffix) for suffix in
                                     ('-compat', '-source', '-saved/v0001'))
            selection = read(compat / 'candidate-selection.json')
            source_selection = read(source / 'candidate-selection.json')
            proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
            report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
            assert selection['manifest_sha256'] == source_selection['manifest_sha256'] == digest
            assert selection['case_id'] == case and selection['candidate_id'] == candidate
            assert selection['construction_sha256'] == proof['construction_sha256'] == \
                processed['analysis_revision']['construction_sha256'] == selected['construction_sha256']
            assert proof['passed'] is True and CHECKS <= set(proof['checks'])
            assert proof['case_id'] == case and proof['candidate_id'] == candidate
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
            measurement = report['measurements']['surveyed_pavement_contact']
            value = measurement['value']
            assert value['measured_contact'] is (count == 300)
            assert value['requested_contact_matched'] is True
            assert len(value['contact_frames']) == count
            control = report['measurements']['control_actor_vicinity']['value']
            assert control['actor_near_surveyed_pavement_frames'] == 600
            assert control['control_content_verified'] is False
            assert control['control_kind'] == 'highway_closed_sign'
            for name, source_hash in measurement['sources'].items():
                assert sha(source / name) == processed['original_source_hashes'][name] == source_hash
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'contact_frames': count,
                         'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                         'saved_receipt_sha256': sha(saved / 'processing.json')})
        assert len(configs) == 4
    return {'manifest_sha256': digest, 'candidate_count': len(rows),
            'passed': True, 'diagnostic_only': True,
            'physical_or_legal_acceptance_claimed': False, 'rows': rows}


if __name__ == '__main__':
    target = PACKAGE / 'update119-combined-highway-closed-sign-pair-audit.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_count': 8, 'passed': True,
                      'audit_sha256': sha(target)}, sort_keys=True))
