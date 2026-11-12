"""Full decoded delivery path with explicitly nonoriginal, source-shaped data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/pipeline'))

from delivery_audit import CAMERAS, ORIGINALS, VIEW_SUBJECTS, audit_complete, sha
from comparison_audit import load_original
import test_physical_fixture_audit as physical_tests


class PositiveDeliveryShapeTest(unittest.TestCase):
    def make_shape(self, root, case_id='case', overlap=5.2, stop_x=0.0):
        attempt, owner, processing, construction = physical_tests.PhysicalFixtureAuditTests().make_chain(
            root, 'complete_motion', case_id=case_id)
        (attempt / 'capture/manifest.json').write_text(json.dumps({
            'extraction_confirmed': True, 'frames': 480,
            'synthetic_diagnostic': False, 'source_shaped_unit_test': True}))
        (attempt / 'road_geometry.json').write_text(json.dumps({
            'native_map_sha256': 'unit-map-only', 'source_shaped_unit_test': True}))
        (attempt / 'config.json').write_text(json.dumps({
            'case_id': case_id, 'candidate_id': 'primary', 'cell_id': 'C10014',
            'law_id': 'NRS-484B-477-2', 'actor': 'motor_vehicle_driver',
            'duration_s': 24, 'rate_hz': 20, 'cameras': list(CAMERAS)}))
        (attempt / 'native-construction-context.json').write_text(json.dumps({
            'case_id': case_id, 'native_weather_readback': {'sun_altitude_angle': 45},
            'vehicle_blueprint': 'unit-blueprint',
            'controller_knobs': {'target_speed_mps': 5},
            'requested_stop_x_m': float(stop_x),
            'requested_route_points': 100 if stop_x == -12 else 220}))
        media = root / 'source-shaped.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'color=c=blue:s=16x16:r=20:d=24',
            '-frames:v', '480', '-an', '-c:v', 'ffv1', str(media)],
            check=True, timeout=60)
        for name in CAMERAS:
            (attempt / (name + '.mkv')).write_bytes(media.read_bytes())
        primary = attempt / 'primary.mkv'
        primary.write_bytes(media.read_bytes())
        mapping = [json.loads(line) for line in
                   (attempt / 'video_frames.jsonl').read_text().splitlines()]
        core = attempt / 'core-trace.json'
        core.write_text(json.dumps({'scenes': [
            {'t': round(row['time_s'] * 1000)} for row in mapping]}))
        result_path = root / 'saved/v0001/analysis/result.json'
        result = json.loads(result_path.read_text())
        source_hash = {'native_samples.jsonl': sha(attempt / 'native_samples.jsonl')}
        result['setup_confirmed'] = False
        result['measured_values'] = {'max_entrance_overlap_m': overlap}
        result['physical_checks'] = {name: {
            'status': 'unverified' if name == 'setup' else 'met',
            'method': 'source-shaped unit test only', 'sources': source_hash}
            for name in ('setup', 'target', 'maneuver', 'attempt')}
        result_path.write_text(json.dumps(result))
        (attempt / 'result.json').write_bytes(result_path.read_bytes())
        seal_path = attempt / 'capture-seal.json'
        seal = json.loads(seal_path.read_text())
        seal['physical_acceptance_claimed'] = False
        sealed_names = {'runner.py', 'construction.json', 'config.json',
                        'native-construction-context.json', *ORIGINALS,
                        *(name + '.mkv' for name in CAMERAS)}
        seal['sources'] = {name: sha(attempt / name) for name in sealed_names}
        seal_path.write_text(json.dumps(seal))
        exit_path = attempt / 'native-exit.json'
        exit_record = json.loads(exit_path.read_text())
        exit_record['capture_seal_sha256'] = sha(seal_path)
        exit_path.write_text(json.dumps(exit_record))
        owner_record = json.loads(owner.read_text())
        owner_record['native_exit_sha256'] = sha(exit_path)
        owner.write_text(json.dumps(owner_record))
        receipt = json.loads(processing.read_text())
        receipt['original_source_hashes'] = seal['sources']
        receipt['result_sha256'] = sha(result_path)
        receipt['missing_evidence'] = False
        processing.write_text(json.dumps(receipt))
        property_source = root / 'property-source.txt'
        property_source.write_text('source-shaped unit test only')
        access = root / 'access-review.json'
        access.write_text(json.dumps({
            'format': 'c10014-original-access-review', 'case_id': case_id,
            'source_kind': 'source_shaped_unit_test', 'reviewer': 'CPU test',
            'method': 'unit shape only', 'property_access_id': 'unit-access',
            'road_geometry_sha256': sha(attempt / 'road_geometry.json'),
            'native_map_sha256': 'unit-map-only',
            'alley_design_confirmed': True,
            'abutting_property_access_confirmed': True,
            'entrance_boundary_confirmed': True,
            'property_source': {'path': str(property_source),
                                'sha256': sha(property_source)}}))
        pixel = root / 'pixel-review.json'
        pixel.write_text(json.dumps({
            'format': 'c10014-original-source-pixel-review', 'case_id': case_id,
            'frames': 480, 'reviewer': 'CPU test', 'method': 'unit shape only',
            'source_kind': 'source_shaped_unit_test',
            'primary_sha256': sha(primary),
            'views': {name: {'video_sha256': sha(attempt / (name + '.mkv')),
                'subjects_visible': sorted(VIEW_SUBJECTS[name]),
                'reviewed_stationary_frames': 40, 'limitations': ['synthetic pixels']}
                for name in CAMERAS}}))
        return attempt, owner, processing.parent, construction, pixel, access, primary, core

    def test_full_decode_path_is_test_only_and_rejects_changed_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt, owner, saved, construction, pixel, access, primary, core = (
                self.make_shape(root))
            args = (attempt, saved, owner, 'case', construction, pixel, access,
                    primary, core, root / 'decode', 'unit-job', 1, 'unit-recording')
            result = audit_complete(*args, test_shape=True)
            self.assertFalse(result['passed'])
            self.assertTrue(result['source_shaped_unit_test'])
            self.assertEqual(result['frames'], 480)
            shape_receipt = root / 'source-shaped-audit.json'
            shape_receipt.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'independent original delivery'):
                load_original(shape_receipt, 'case')
            result['passed'] = True
            shape_receipt.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'independent original delivery'):
                load_original(shape_receipt, 'case')
            with self.assertRaisesRegex(ValueError, 'Source-shaped unit test'):
                audit_complete(*args)
            scenes = json.loads(core.read_text())
            scenes['scenes'][5]['t'] += 50
            core.write_text(json.dumps(scenes))
            with self.assertRaisesRegex(ValueError, 'Core trace does not join'):
                audit_complete(*args, test_shape=True)


if __name__ == '__main__':
    unittest.main()
