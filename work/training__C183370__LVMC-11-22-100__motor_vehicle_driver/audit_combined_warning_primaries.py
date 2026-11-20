"""Independently compare the combined-manifest warning-person primaries."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = PACKAGE / 'draft-combined-capture-manifest.json'
    manifest = read(manifest_path)
    digest = sha(manifest_path)
    rows = []
    for short, count in (('reference', 300), ('contrast', 0)):
        case = PACKAGE.name + '__' + short
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        base = REPO / '.runtime-work' / ('c183370-update116-combined-' + short + '-primary')
        compat, source, saved = (Path(str(base) + suffix) for suffix in
                                 ('-compat', '-source', '-saved/v0001'))
        selection = read(compat / 'candidate-selection.json')
        proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
        report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
        assert selection['manifest_sha256'] == read(source / 'candidate-selection.json')['manifest_sha256'] == digest
        assert selection['construction_sha256'] == proof['construction_sha256'] == \
            processed['analysis_revision']['construction_sha256'] == entry['construction_sha256']
        assert proof['passed'] is True and proof['case_id'] == case and proof['candidate_id'] == 'primary'
        assert proof['negative_removed'] == 'live-readback.json'
        assert 'Missing required source: live-readback.json' in \
            (compat / 'negative-analysis.log').read_text()
        assert processed['passed'] is True and processed['recorded_only'] is True
        assert processed['originals_preserved'] is True and processed['missing_evidence'] is False
        assert processed['timestamp_joins']['passed'] is True and processed['timestamp_joins']['frames'] == 600
        assert processed['final_video_checks']['passed'] is True
        assert report['analysis_complete'] is True and report['diagnostic_fixture'] is True
        assert report['physical_acceptance_claimed'] is False
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        measured = report['measurements']['surveyed_pavement_contact']['value']
        assert measured['measured_contact'] is (count == 300)
        assert measured['requested_contact_matched'] is True
        assert len(measured['contact_frames']) == count
        assert report['measurements']['warning_person_vicinity']['value'][
            'person_near_surveyed_pavement_frames'] == 600
        for name, source_hash in report['measurements']['surveyed_pavement_contact']['sources'].items():
            assert sha(source / name) == processed['original_source_hashes'][name] == source_hash
        rows.append({'case_id': case, 'contact_frames': count,
                     'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                     'saved_receipt_sha256': sha(saved / 'processing.json')})
    return {'manifest_sha256': digest, 'primary_count': 2, 'passed': True,
            'diagnostic_only': True, 'physical_or_legal_acceptance_claimed': False,
            'rows': rows}


if __name__ == '__main__':
    target = PACKAGE / 'update116-combined-warning-primary-audit.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'primary_count': 2, 'passed': True,
                      'audit_sha256': sha(target)}, sort_keys=True))
