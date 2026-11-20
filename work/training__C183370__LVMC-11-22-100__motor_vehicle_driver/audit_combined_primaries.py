"""Independently audit all ten primary diagnostic chains under one manifest."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
            'selected_measurements', 'negative_case_source'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest, digest = read(MANIFEST), sha(MANIFEST)
    assert len(manifest['cases']) == 10
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.removeprefix(PACKAGE.name + '__')
        if short == 'barrier_crossing':
            base = REPO / '.runtime-work/c183370-update115-combined-barrier-primary'
        else:
            base = REPO / '.runtime-work' / ('c183370-update116-combined-' + short + '-primary')
        compat, source, saved = (Path(str(base) + suffix) for suffix in
                                 ('-compat', '-source', '-saved/v0001'))
        selection = read(compat / 'candidate-selection.json')
        proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
        report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
        assert selection['manifest_sha256'] == read(source / 'candidate-selection.json')['manifest_sha256'] == digest
        assert selection['case_id'] == case and selection['candidate_id'] == 'primary'
        assert selection['construction_sha256'] == proof['construction_sha256'] == \
            processed['analysis_revision']['construction_sha256'] == entry['construction_sha256']
        assert proof['passed'] is True and REQUIRED <= set(proof['checks'])
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
        measurement = report['measurements']['surveyed_pavement_contact']
        value = measurement['value']
        crossing = short not in ('contrast', 'barrier_avoidance',
                                 'warning_sign_avoidance', 'highway_closed_sign_avoidance')
        assert value['measured_contact'] is crossing
        assert value['requested_contact_matched'] is True
        assert len(value['contact_frames']) == (300 if crossing else 0)
        for name, source_hash in measurement['sources'].items():
            assert sha(source / name) == processed['original_source_hashes'][name] == source_hash
        if short in ('reference', 'contrast'):
            assert report['measurements']['warning_person_vicinity']['value'][
                'person_near_surveyed_pavement_frames'] == 600
        else:
            control = report['measurements']['control_actor_vicinity']['value']
            assert control['actor_near_surveyed_pavement_frames'] == 600
            assert control['control_content_verified'] is False
        if short.startswith('employee_exception_'):
            route = short.removeprefix('employee_exception_')
            plan = read(source / 'live-readback.json')['plan']
            assert plan['cases'][route]['operator_activity_source'] == \
                'synthetic_fixture_only_' + route + '_activity_unverified'
            assert plan['source_references']['employee_activity_source'] != \
                plan['source_references']['nonemployee_activity_source']
        rows.append({'case_id': case, 'construction_sha256': entry['construction_sha256'],
                     'contact_frames': len(value['contact_frames']),
                     'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                     'saved_receipt_sha256': sha(saved / 'processing.json')})
    return {'manifest_sha256': digest, 'primary_count': len(rows),
            'passed': True, 'diagnostic_only': True,
            'physical_or_legal_acceptance_claimed': False, 'rows': rows}


if __name__ == '__main__':
    target = PACKAGE / 'update117-combined-primaries-audit.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'primary_count': 10, 'passed': True,
                      'audit_sha256': sha(target)}, sort_keys=True))
