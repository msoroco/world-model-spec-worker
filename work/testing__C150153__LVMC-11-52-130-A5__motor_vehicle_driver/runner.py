"""Run one original source-reviewed sidewalk-elevator Native case."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from native_case_runner import run_case
from native_camera_capture import capture as capture_with_cameras
from reviewed_site import verify

CASE_ID = 'testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver__front_park'
SITE_SHA256 = None
BODY_LENGTH_M = 4.0
CAMERA_LATERAL_OFFSET_M = 0.0

def _verified_original(packet, source_root):
    reviewed = verify(packet, source_root)
    provenance = reviewed.get('source_provenance')
    if (not isinstance(provenance, dict) or
            provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed site provenance required')
    return reviewed

def run(adapter, packet, source_root, output):
    _verified_original(Path(packet), Path(source_root))
    if not hasattr(adapter, 'provenance') or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    return run_case(adapter, Path(packet), Path(source_root), CASE_ID,
                    BODY_LENGTH_M, Path(output))

def run_original_capture(adapter, packet, source_root, output_dir):
    _verified_original(Path(packet), Path(source_root))
    if not hasattr(adapter, 'provenance') or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    return capture_with_cameras(adapter, Path(packet), Path(source_root), CASE_ID,
                                BODY_LENGTH_M, Path(output_dir),
                                camera_lateral_offset_m=CAMERA_LATERAL_OFFSET_M)

def check():
    root = Path(__file__).resolve().parent
    scene = json.loads((root / 'scene.json').read_text())
    config = json.loads((root / 'config.json').read_text())
    if scene.get('case_id') != CASE_ID or config.get('selected_case_id') != CASE_ID:
        raise ValueError('selected exact case differs')
    if scene.get('source_status') != 'original_reviewed_site_required_at_capture':
        raise ValueError('original reviewed site capture requirement missing')
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
