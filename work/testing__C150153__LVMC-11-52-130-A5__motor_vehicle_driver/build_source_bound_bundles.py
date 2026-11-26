"""Generate exact Native bundle proposals from a verified original site packet.

Generated proposals are not selected or ready until their original-site source
custody, adapter execution and delivery proofs pass on the pinned runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reviewed_site import exact_specs


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ("parking.py", "reviewed_site.py", "native_case_runner.py",
           "native_history_capture.py", "saved_audit.py",
           "independent_delivery_audit.py", "seal_original_capture.py",
           "physical_review.py", "saved_finalizer.py", "comparison_audit.py",
           "physical_outcomes.py", "physical_preparation.py")
MODULES += ("native_camera_capture.py",)
MODULES += ("analysis.py",)
PLAN = json.loads((HERE / 'case-plan.json').read_text())

RUNNER = '''"""Run one original source-reviewed sidewalk-elevator Native case."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from native_case_runner import run_case
from native_camera_capture import capture as capture_with_cameras
from reviewed_site import verify

CASE_ID = {case_id!r}
SITE_SHA256 = {site_sha256!r}
BODY_LENGTH_M = {body_length_m!r}

def run(adapter, packet, source_root, output):
    if hashlib.sha256(Path(packet).read_bytes()).hexdigest() != SITE_SHA256:
        raise ValueError('reviewed original site packet changed')
    verify(Path(packet), Path(source_root))
    if not hasattr(adapter, 'provenance') or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    return run_case(adapter, Path(packet), Path(source_root), CASE_ID,
                    BODY_LENGTH_M, Path(output))

def run_original_capture(adapter, packet, source_root, output_dir):
    if hashlib.sha256(Path(packet).read_bytes()).hexdigest() != SITE_SHA256:
        raise ValueError('reviewed original site packet changed')
    verify(Path(packet), Path(source_root))
    if not hasattr(adapter, 'provenance') or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    return capture_with_cameras(adapter, Path(packet), Path(source_root), CASE_ID,
                                BODY_LENGTH_M, Path(output_dir))

def check():
    root = Path(__file__).resolve().parent
    scene = json.loads((root / 'scene.json').read_text())
    config = json.loads((root / 'config.json').read_text())
    if scene.get('case_id') != CASE_ID or config.get('selected_case_id') != CASE_ID:
        raise ValueError('selected exact case differs')
    if scene.get('reviewed_site_packet_sha256') != SITE_SHA256:
        raise ValueError('reviewed site packet binding differs')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45 or len(config.get('cameras', [])) != 4:
        raise ValueError('original capture specification differs')
    return scene

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-packet', type=Path,
                        default=os.environ.get('C150153_REVIEWED_SITE_PACKET'))
    parser.add_argument('--source-root', type=Path,
                        default=os.environ.get('C150153_ORIGINAL_SOURCE_ROOT'))
    parser.add_argument('--adapter-module', type=Path,
                        default=os.environ.get('C150153_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    check()
    if args.check:
        print('source-bound exact case preflight passed: ' + CASE_ID)
        return
    if not all((args.reviewed_packet, args.source_root, args.adapter_module,
                args.output_dir, args.host, args.port)):
        raise ValueError('original source and Native adapter arguments required')
    spec = importlib.util.spec_from_file_location('original_elevator_adapter', args.adapter_module)
    if spec is None or spec.loader is None:
        raise ValueError('original adapter module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, 'open_native_adapter'):
        raise ValueError('original Native adapter factory missing')
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        result = run_original_capture(adapter, args.reviewed_packet, args.source_root, args.output_dir)
        print(result)
    finally:
        adapter.close()

if __name__ == '__main__':
    main()
'''

TEST = '''import unittest
import runner

class OriginalBundleTest(unittest.TestCase):
    def test_exact_source_bound_preflight(self):
        self.assertEqual(runner.check()['case_id'], runner.CASE_ID)

    def test_original_capture_arguments_required(self):
        from unittest.mock import patch
        with patch('sys.argv', ['runner.py']):
            with self.assertRaisesRegex(ValueError, 'original source and Native adapter'):
                runner.main()
'''


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def generate(packet: Path, source_root: Path, body_length_m: float,
             output_dir: Path) -> dict:
    output_dir = Path(output_dir).resolve()
    if not output_dir.is_relative_to((ROOT / '.runtime-work').resolve()):
        raise ValueError('source-bound draft output must be under .runtime-work')
    if output_dir.exists():
        raise ValueError('source-bound draft output already exists')
    specs = exact_specs(packet, source_root, body_length_m)
    site_sha = _sha(Path(packet).read_bytes())
    module_files = {name: (HERE / name).read_text() for name in MODULES}
    entries = []
    output_dir.mkdir(parents=True)
    for item in specs['cases']:
        case_id = item['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        runner = RUNNER.format(case_id=case_id, site_sha256=site_sha,
                               body_length_m=body_length_m)
        scene = {'assignment_id': HERE.name, 'case_id': case_id,
                 'kind': kind, 'reviewed_site_packet_sha256': site_sha,
                 'capture_frames': 900, 'capture_rate_hz': 20,
                 'commanded_body_interval_m': item['commanded_body_interval_m'],
                 'physical_acceptance': False, 'legal_judgment': None}
        config = {'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                  'actor': 'motor_vehicle_driver', 'selected_case_id': case_id,
                  'supported_case_ids': [item['case_id'] for item in specs['cases']],
                  'rate_hz': 20, 'duration_s': 45,
                  'required_atoms': [], 'source_packets': [],
                  'recording_description': next(c['recording_description'] for c in PLAN['cases'] if c['case_id'] == case_id),
                  'case': {'recording_description': next(c['recording_description'] for c in PLAN['cases'] if c['case_id'] == case_id)},
                  'cameras': [
                      {'name': 'overview', 'width': 1920, 'height': 1080,
                       'pose_strategy': 'source-reviewed frontage overview', 'fov_deg': 90},
                      {'name': 'approach', 'width': 1280, 'height': 720,
                       'pose_strategy': 'source-reviewed one-way approach', 'fov_deg': 90},
                      {'name': 'reference_corner', 'width': 1280, 'height': 720,
                       'pose_strategy': 'source-reviewed five-foot reference corner', 'fov_deg': 90},
                      {'name': 'driver_reference', 'width': 1280, 'height': 720,
                       'pose_strategy': 'source-reviewed driver and direction view', 'fov_deg': 90}]}
        files = {'runner.py': runner, 'scene.json': json.dumps(scene, indent=2) + '\n',
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'tests/test_bundle.py': TEST,
                 **module_files}
        construction = {'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                        'actor': 'motor_vehicle_driver', 'case_id': case_id,
                        'entrypoint': 'runner.py', 'source_kind': 'original_reviewed_site',
                        'recording_description': next(c['recording_description'] for c in PLAN['cases'] if c['case_id'] == case_id),
                        'measurement_plan': {'method': 'saved_finalizer.finalize', 'source': 'sealed original Native history'},
                        'static_checks': ['reviewed site and exact case binding', '20 Hz and 900 frames'],
                        'termination_rules': {'frame_count': 900},
                        'mechanisms': ['native_case_runner.run_case', 'physical_preparation.prepare'],
                        'files': [{'path': path, 'content': text}
                                  for path, text in files.items()]}
        raw = (json.dumps(construction, indent=2, sort_keys=True) + '\n').encode()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('source-bound bundle exceeds returned-file limit')
        target = output_dir / ('construction-' + kind + '.json')
        target.write_bytes(raw)
        entries.append({'case_id': case_id, 'construction': target.name,
                        'construction_sha256': _sha(raw),
                        'physical_risk': item['physical_risk']})
    index = {'format': 'sidewalk-elevator-source-bound-draft',
             'status': 'unselected_original_capture_pending',
             'assignment_id': HERE.name, 'reviewed_site_packet_sha256': site_sha,
             'cases': entries}
    (output_dir / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--body-length-m', type=float, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.packet, args.source_root, args.body_length_m,
                              args.output_dir), indent=2))


if __name__ == '__main__':
    main()
