"""Bind all selected long schedules to saved measurements and generator bounds."""
import hashlib
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect as inspect_generator

spec = importlib.util.spec_from_file_location('exception_duration', ROOT / 'native/exception_duration.py')
duration_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(duration_module)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config(construction):
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = read(manifest_path)
    records = []
    boundaries = {'below': 0, 'at': 0, 'above': 0}
    for entry in manifest['cases']:
        slug = entry['case_id'].split('__')[-1]
        if not slug.startswith(('tour_bus_', 'shuttle_bus_', 'rtc_bus_', 'limo_')):
            continue
        index_path = ROOT / ('current-' + slug.replace('_', '-') + '-long-saved-index.json')
        index = read(index_path)
        assert index['selected_manifest_sha256'] == sha(manifest_path)
        assert index['passed_candidates'] == 4
        candidates = [('primary', entry['construction'], entry['construction_sha256'])]
        candidates.extend((c['id'], c['construction'], c['construction_sha256'])
                          for c in entry['candidates'])
        assert {row['candidate_id'] for row in index['cases']} == {c[0] for c in candidates}
        for candidate, relative, expected_sha in candidates:
            construction_path = ROOT / relative
            assert sha(construction_path) == expected_sha
            cfg = config(read(construction_path))
            schedule = duration_module.plan(cfg, cfg['requested_approach_frames'])
            assert cfg['case_id'] == entry['case_id']
            assert cfg['capture_frames'] == schedule['capture_frames']
            assert cfg['requested_boundary'] == schedule['requested_boundary']
            expected_boundary = ('at' if slug.endswith(('_at', '_no_loading')) else
                                 'above' if slug.endswith('_above') else 'below')
            assert schedule['requested_boundary'] == expected_boundary
            saved = next(row for row in index['cases'] if row['candidate_id'] == candidate)
            assert saved['construction_sha256'] == expected_sha
            assert saved['frames'] == schedule['capture_frames']
            summary_path = ROOT / saved['summary']
            assert sha(summary_path) == saved['summary_sha256']
            summary = read(summary_path)
            assert summary['passed'] and summary['final_decode_frames'] == schedule['capture_frames']
            assert not summary['original_native_observed'] and summary['source_kind'] == 'synthetic_native_sample'
            processing = REPO / summary['processing_ignored_path']
            assert sha(processing) == summary['processing_sha256']
            report = read(processing.parent / 'analysis/analysis-report.json')
            observation = report['measurements']['signed_curb_observation']['value']
            measured = Decimal(str(observation['red_curb_stationary_duration_s']))
            requested = Decimal(str(cfg['requested_stationary_duration_s']))
            assert measured == requested
            assert observation['frames'] == schedule['capture_frames']
            assert observation['duration_relative_to_30_minutes'] == expected_boundary
            assert (measured < 1800 if expected_boundary == 'below' else
                    measured == 1800 if expected_boundary == 'at' else measured > 1800)
            assert observation['legal_verdict'] is None
            boundaries[expected_boundary] += 1
            records.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': expected_sha,
                            'saved_summary_sha256': saved['summary_sha256'],
                            'analysis_report_sha256': sha(processing.parent / 'analysis/analysis-report.json'),
                            'frames': schedule['capture_frames'],
                            'stationary_first_frame': schedule['stationary_first_frame'],
                            'stationary_last_frame': schedule['stationary_last_frame'],
                            'measured_duration_s': str(measured), 'boundary': expected_boundary})
    assert len(records) == 64 and boundaries == {'below': 16, 'at': 32, 'above': 16}
    video = {'path': 'diagnostic.mkv', 'frames': 2000, 'width': 64,
             'height': 64, 'fps': 20, 'color': 'black'}
    assert inspect_generator({'files': {}, 'graphs': [], 'videos': [video]}) == ['diagnostic.mkv']
    rejected = 0
    for bad in (2001, 36120, 36121, 36122):
        try:
            inspect_generator({'files': {}, 'graphs': [], 'videos': [{**video, 'frames': bad}]})
        except ValueError as error:
            assert 'Invalid bounded diagnostic video parameters' in str(error)
            rejected += 1
    assert rejected == 4
    for value in ('1799.951', '0', '-1', 'NaN'):
        try:
            duration_module.plan({'case_id': records[0]['case_id'],
                                  'requested_stationary_duration_s': value})
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid duration accepted: ' + value)
    print(json.dumps({'format': 'c150142-current-long-timing-proof-v1',
                      'passed': True, 'manifest_sha256': sha(manifest_path),
                      'duration_module_sha256': sha(ROOT / 'native/exception_duration.py'),
                      'fixture_generator_bounded_max_frames': 2000,
                      'fixture_generator_rejected_frames': [2001, 36120, 36121, 36122],
                      'negative_duration_inputs_rejected': ['1799.951', '0', '-1', 'NaN'],
                      'candidate_count': len(records), 'boundary_counts': boundaries,
                      'records': records, 'official_recipe_compatibility_passed': 0,
                      'original_native_observed': False,
                      'physical_acceptance_claimed': False,
                      'legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
