"""Diagnostic CPU proof for independent source and four-camera decode audit."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('device_delivery_probe', ROOT / 'delivery_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id: str, kind: str, attempt: Path) -> dict:
    if kind not in ('positive', 'negative'):
        raise ValueError('unknown delivery proof mode')
    source = ROOT / ('physical-source-' + case_id.split('__')[-1] + '-complete_motion.json')
    packet = json.loads(source.read_text())
    packet.update(map_sha256='1' * 64, route_sha256='2' * 64,
                  highway_status={'source_sha256': '3' * 64}, duration_s=45.0,
                  camera_plan_sha256='8' * 64)
    packet['device'].update(authority_source_sha256='4' * 64,
                            legal_consistency_source_sha256='5' * 64,
                            display_source_sha256=('7' if case_id.endswith('__neutral_device_turn')
                                                   else '6') * 64)
    for row in packet['frames']:
        row['cameras'] = {name: row['frame'] for name in CAMERAS}
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    native = attempt / 'device-native.json'
    native.write_text(json.dumps(packet, separators=(',', ':')) + '\n')
    first = attempt / 'overview.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=16x16:rate=20', '-frames:v', '900',
                    '-c:v', 'ffv1', str(first)], check=True)
    media = {}
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        if path != first:
            shutil.copy2(first, path)
        media[name] = {'path': path.name, 'sha256': sha(path)}
    manifest = {'case_id': case_id, 'attempt_id': 'cpu-diagnostic-' + case_id.split('__')[-1],
                'recording_id': 'no-original-recording', 'acquisition_kind': 'original_native',
                'native': {'path': native.name, 'sha256': sha(native)}, 'media': media}
    if kind == 'negative':
        manifest['media']['approach']['sha256'] = '0' * 64
    (attempt / 'saved-sources.json').write_text(json.dumps(manifest, indent=2) + '\n')
    profile = {name: (16, 16) for name in CAMERAS}
    result = module.audit(attempt, case_id, diagnostic=True, profile=profile)
    if kind == 'negative':
        raise ValueError('negative media corruption was accepted')
    if result['actual_pixels'] or result['physical_completion']:
        raise ValueError('diagnostic proof claimed original physical acceptance')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.attempt), sort_keys=True))


if __name__ == '__main__':
    main()
