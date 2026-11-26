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
           "physical_review.py", "saved_finalizer.py", "comparison_audit.py")

RUNNER = '''"""Run one original source-reviewed sidewalk-elevator Native case."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
from native_case_runner import run_case
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewed-packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--adapter-module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('original_elevator_adapter', args.adapter_module)
    if spec is None or spec.loader is None:
        raise ValueError('original adapter module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, 'open_native_adapter'):
        raise ValueError('original Native adapter factory missing')
    adapter = module.open_native_adapter()
    try:
        result = run(adapter, args.reviewed_packet, args.source_root, args.output)
        print(result)
    finally:
        adapter.close()

if __name__ == '__main__':
    main()
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
        files = {'runner.py': runner, 'scene.json': json.dumps(scene, indent=2) + '\n',
                 **module_files}
        construction = {'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                        'actor': 'motor_vehicle_driver', 'case_id': case_id,
                        'entrypoint': 'runner.py', 'source_kind': 'original_reviewed_site',
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
