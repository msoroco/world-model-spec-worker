"""Audit current C183370 synthetic proof matrix without physical claims."""
import hashlib
import json
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
REPO=PACKAGE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=read(PACKAGE/'draft-measured-candidate-manifest.json')
    entries={e['case_id'].rsplit('__',1)[1]:e for e in manifest['cases']}
    matrix=[]
    for case in ('reference','contrast'):
        entry=entries[case]
        expected_contact=case=='reference'
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            prefix='c183370-update105-'+case+'-'+candidate
            compatibility=REPO/'.runtime-work'/(prefix+'-compat'+('-r2' if case=='reference' and candidate=='primary' else ''))
            saved=REPO/'.runtime-work'/(prefix+'-saved')/'v0001'
            if candidate=='primary':
                construction=entry['construction_sha256']
                offline_name='update105-'+case+'-primary-offline'+('-r1' if case=='reference' else '')+'.log'
            else:
                construction=next(c['construction_sha256'] for c in entry['candidates'] if c['id']==candidate)
                offline_name='update105-'+case+'-'+candidate+'-offline.log'
            offline=PACKAGE/offline_name
            compat_log=PACKAGE/('update105-'+case+'-'+candidate+'-compat'+('-r2' if case=='reference' and candidate=='primary' else '')+'.log')
            saved_log=PACKAGE/('update105-'+case+'-'+candidate+'-saved.log')
            proof=read(compatibility/'compatibility.json')
            processed=read(saved/'processing.json')
            report=read(saved/'analysis/analysis-report.json')
            result=read(saved/'analysis/result.json')
            expected={'actual_analysis','native_validation','mandatory_observations',
                      'lean_decoder','render','final_decode','acquisition_unchanged',
                      'derived_outputs_rebuilt','four_camera_sources',
                      'selected_measurements','negative_case_source'}
            assert proof['passed'] is True and expected<=set(proof['checks'])
            assert proof['case_id']==entry['case_id'] and proof['candidate_id']==candidate
            assert proof['construction_sha256']==construction
            assert proof['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
            assert proof['negative_removed']=='live-readback.json'
            assert 'Missing required source: live-readback.json' in (compatibility/'negative-analysis.log').read_text()
            assert processed['passed'] is True and processed['missing_evidence'] is False
            assert processed['originals_preserved'] is True and processed['timestamp_joins']['frames']==600
            assert processed['timestamp_joins']['passed'] is True
            assert processed['final_video_checks']['passed'] is True
            assert processed['analysis_revision']['construction_sha256']==construction
            assert report['analysis_complete'] is True
            assert report['provenance_kind']=='synthetic_fixture' and report['diagnostic_fixture'] is True
            assert result['provenance_kind']=='synthetic_fixture' and result['diagnostic_fixture'] is True
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            measure=report['measurements']['surveyed_pavement_contact']['value']
            assert measure['measured_contact'] is expected_contact
            assert measure['requested_contact_matched'] is True
            assert len(measure['contact_frames'])==(300 if expected_contact else 0)
            assert report['measurements']['warning_person_vicinity']['value']['person_near_surveyed_pavement_frames']==600
            for name,checksum in report['measurements']['surveyed_pavement_contact']['sources'].items():
                assert processed['original_source_hashes'][name]==checksum
            matrix.append({'case':case,'candidate':candidate,
                           'construction_sha256':construction,
                           'offline_log_sha256':sha(offline),
                           'compatibility_log_sha256':sha(compat_log),
                           'compatibility_receipt_sha256':sha(compatibility/'compatibility.json'),
                           'saved_log_sha256':sha(saved_log),
                           'saved_receipt_sha256':sha(saved/'processing.json'),
                           'contact_frames':len(measure['contact_frames']),
                           'source_frames':processed['timestamp_joins']['frames'],
                           'originals_preserved':True,
                           'physical_acceptance_claimed':False})
    return {'format':'c183370-current-synthetic-proof-matrix-v1',
            'scope':'diagnostic software compatibility only',
            'manifest_sha256':sha(PACKAGE/'draft-measured-candidate-manifest.json'),
            'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'all_eight_passed':True,'native_capture_claimed':False,
            'physical_acceptance_claimed':False,'cases':matrix}


if __name__=='__main__':
    target=PACKAGE/'update105-selected-diagnostic-matrix.json'
    target.write_text(json.dumps(audit(),indent=2,sort_keys=True)+'\n')
