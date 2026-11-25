"""Saved analysis and pinned Native validator consume the same original bundle."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path[:0] = [str(ROOT), str(REPO / 'runtime/scenario_pipeline')]
from analysis import analyze
from canonical_crest import publish
from saved_crest_audit import ASSIGNMENT
from saved_crest_bundle import assemble
from test_saved_crest_media import media_fixture


class SavedAnalysisTests(unittest.TestCase):
    def test_source_bound_analysis_native_validation_and_missing_limit(self):
        self.assertIn('.runtime-work', Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).parts)
        scratch = REPO / '.runtime-work/c104084-current'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            fixture = media_fixture(source)
            motion = json.loads((source / 'motion.json').read_text())
            for index, row in enumerate(motion):
                row['position'] = {'x': float(index), 'y': 0.0, 'z': 1.0}
                row['heading_deg'] = 0.0
            (source / 'motion.json').write_text(json.dumps(motion) + '\n')
            native = source / 'native-map.xodr'
            native.write_text('diagnostic loaded map\n')
            spec = {'profile': 'early_decrease', 'acquisition_kind': 'original_native',
                    'native_map_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
                    'native_capture_ref': 'diagnostic-only',
                    'approach_start_m': fixture['approach_start_m'],
                    'camera_dimensions': fixture['camera_dimensions'],
                    'sources': {'native_map_source': str(native),
                        **{key: str(source / fixture[key]['path']) for key in
                           ('grade_source', 'motion_source', 'context_source',
                            'other_route_source', 'frame_map_source', 'prescribed_limit_source')}},
                    'cameras': {key: str(source / value['path']) for key, value in
                                fixture['camera_sources'].items()}}
            case = ASSIGNMENT + '__early_decrease'
            bundle = root / 'bundle'
            assemble(spec, bundle, expected_case=case)
            attempt = (root / 'attempt').resolve()
            attempt.mkdir()
            for name in ('construction.json', 'config.json', 'runner.py'):
                (attempt / name).write_bytes((ROOT / name).read_bytes())
            publish(bundle, attempt, case)
            report = analyze(attempt, attempt / 'analysis-report.json')
            self.assertEqual(set(report['measurements']),
                             {'prescribed_limit_measurement', 'crest_measurement',
                              'speed_decrease_measurement', 'other_vehicle_measurement'})
            from batch_pipeline.carla import validate_attempt
            proposal = next(item for item in json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
                            if item['case_id'] == case)
            construction = json.loads((ROOT / 'construction.json').read_text())
            verified = validate_attempt(attempt, {'case': proposal,
                'cell': {'cell_id': 'C104084'}, 'actor': 'motor_vehicle_driver'},
                construction, {'recorded_exit_code': 0}, {})
            self.assertEqual(verified['case_id'], case)
            self.assertTrue(verified['rebuild_required'])
            (attempt / 'capture/crest-source/reviewed-limit.json').unlink()
            negative = (root / 'negative').resolve()
            negative.mkdir()
            for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
                (negative / name).write_bytes((attempt / name).read_bytes())
            import shutil
            shutil.copytree(attempt / 'capture', negative / 'capture')
            with self.assertRaisesRegex(ValueError,
                'Missing required source: capture/crest-source/reviewed-limit.json'):
                analyze(negative, negative / 'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
