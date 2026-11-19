"""Independently audit all employee CPU candidate chains under the final manifest."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
ROUTES = ('employee_crossing', 'nonemployee_crossing')
KINDS = ('employee_exception',)
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(update='update114'):
    manifest_path = PACKAGE / 'draft-employee-capture-manifest.json'
    manifest, manifest_sha = read(manifest_path), sha(manifest_path)
    expected_checks = {'actual_analysis', 'native_validation',
                       'mandatory_observations', 'lean_decoder', 'render',
                       'final_decode', 'acquisition_unchanged',
                       'derived_outputs_rebuilt', 'four_camera_sources',
                       'selected_measurements', 'negative_case_source'}
    rows = []
    for kind in KINDS:
      for route in ROUTES:
          case = PACKAGE.name + '__' + kind + '_' + route
          entry = next(item for item in manifest['cases'] if item['case_id'] == case)
          configs = set()
          for candidate in CANDIDATES:
              selected = (entry if candidate == 'primary' else
                          next(item for item in entry['candidates'] if item['id'] == candidate))
              construction = read(PACKAGE / selected['construction'])
              config = next(item['content'] for item in construction['files'] if item['path'] == 'config.json')
              configs.add(config)
              base = REPO / '.runtime-work' / ('c183370-' + update + '-employee-proof-' + kind + '-' + route + '-' + candidate)
              compat, source, saved = (Path(str(base) + suffix) for suffix in
                                       ('-compat', '-source', '-saved/v0001'))
              proof, processed = read(compat / 'compatibility.json'), read(saved / 'processing.json')
              report, result = read(saved / 'analysis/analysis-report.json'), read(saved / 'analysis/result.json')
              assert proof['passed'] is True and expected_checks <= set(proof['checks'])
              assert proof['case_id'] == case and proof['candidate_id'] == candidate
              assert proof['construction_sha256'] == selected['construction_sha256']
              assert proof['negative_removed'] == 'live-readback.json'
              assert 'Missing required source: live-readback.json' in (compat / 'negative-analysis.log').read_text()
              assert processed['passed'] is True and processed['missing_evidence'] is False
              assert processed['originals_preserved'] is True
              assert processed['timestamp_joins']['passed'] is True
              assert processed['timestamp_joins']['frames'] == 600
              assert processed['final_video_checks']['passed'] is True
              assert processed['analysis_revision']['construction_sha256'] == selected['construction_sha256']
              assert read(source / 'candidate-selection.json')['manifest_sha256'] == manifest_sha
              readback = read(source / 'live-readback.json')['plan']
              assert readback['control_kind'] == 'employee_exception'
              assert readback['cases'][route]['operator_activity_source'] == (
                  'synthetic_fixture_only_' + route + '_activity_unverified')
              assert readback['source_references']['employee_activity_source'] != (
                  readback['source_references']['nonemployee_activity_source'])
              assert report['analysis_complete'] is True and report['diagnostic_fixture'] is True
              assert result['diagnostic_fixture'] is True and result['accepted'] is False
              assert result['legal_verdict_claimed'] is False
              assert report['physical_acceptance_claimed'] is False
              measurement = report['measurements']['surveyed_pavement_contact']['value']
              assert measurement['measured_contact'] == True
              assert measurement['requested_contact_matched'] is True
              assert len(measurement['contact_frames']) == 300
              for name, digest in report['measurements']['surveyed_pavement_contact']['sources'].items():
                  assert processed['original_source_hashes'][name] == digest
                  assert sha(source / name) == digest
              logs = {name: PACKAGE / ('update113-' + kind + '_' + route + '-' + candidate + '-offline-final.log'
                       if name == 'offline' else update + '-' + kind + '-' + route + '-' + candidate + '-' + name + '.log')
                      for name in ('offline', 'compat', 'stage', 'saved')}
              rows.append({'case_id': case, 'candidate': candidate,
                           'construction_sha256': selected['construction_sha256'],
                           'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                           'saved_receipt_sha256': sha(saved / 'processing.json'),
                           'logs': {name: sha(log) for name, log in logs.items()},
                           'contact_frames': len(measurement['contact_frames']),
                           'source_frames': 600, 'physical_acceptance_claimed': False})
          assert len(configs) == 4
    return {'format': 'c183370-employee-final-candidate-matrix-v1',
            'scope': 'synthetic diagnostic software compatibility only',
            'manifest_sha256': manifest_sha, 'candidate_count': len(rows),
            'all_passed': True, 'original_carla_claimed': False,
            'physical_acceptance_claimed': False, 'cases': rows}


if __name__ == '__main__':
    target = PACKAGE / 'update114-employee-final-candidate-matrix.json'
    target.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
