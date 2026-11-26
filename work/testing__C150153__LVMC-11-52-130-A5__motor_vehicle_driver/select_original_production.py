"""Select source-bound production constructions only from external original review.

Selection establishes source custody and CPU construction identity. It does not
claim Native capture, pixels, physical completion, or legal applicability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from build_source_bound_bundles import generate
from reviewed_site import verify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME_MANIFEST = ROOT / 'runtime/SOURCE-MANIFEST.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(packet_path: Path, source_root: Path, body_length_m: float) -> dict:
    packet_path = Path(packet_path).resolve()
    source_root = Path(source_root).resolve()
    if (packet_path.is_relative_to(ROOT) or source_root.is_relative_to(ROOT)):
        raise ValueError('original reviewed site inputs must be external to worker repository')
    packet = verify(packet_path, source_root)
    provenance = packet.get('source_provenance')
    if (not isinstance(provenance, dict) or provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed site provenance required')
    manifest_path = HERE / 'execution-manifest.json'
    selected_path = HERE / 'production-source-selection.json'
    if manifest_path.exists() or selected_path.exists():
        raise ValueError('refusing to overwrite selected original production sources')
    with TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c150153-original-select-') as temp:
        draft_dir = Path(temp) / 'generated'
        draft = generate(packet_path, source_root, body_length_m, draft_dir)
        if len(draft['cases']) != 12:
            raise ValueError('exact original source selection lacks twelve cases')
        entries = []
        staged = []
        for item in draft['cases']:
            kind = item['case_id'].removeprefix(HERE.name + '__')
            case_dir = HERE / 'cases' / kind
            construction = case_dir / 'construction.original.json'
            contract = case_dir / 'measurement-original.json'
            fallback = case_dir / 'construction.original.fallback1.json'
            if construction.exists() or contract.exists() or fallback.exists():
                raise ValueError('refusing to overwrite original case construction: ' + kind)
            source = draft_dir / item['construction']
            measurement = draft_dir / item['measurement_contract']
            fallback_source = draft_dir / item['candidates'][0]['construction']
            if sha(source) != item['construction_sha256'] or sha(measurement) != item['measurement_contract_sha256']:
                raise ValueError('generated original source construction changed: ' + kind)
            if sha(fallback_source) != item['candidates'][0]['construction_sha256']:
                raise ValueError('generated original fallback construction changed: ' + kind)
            selected = dict(item, construction=str(construction.relative_to(HERE)),
                            measurement_contract=str(contract.relative_to(HERE)))
            selected['candidates'] = [dict(item['candidates'][0],
                                           construction=str(fallback.relative_to(HERE)))]
            selected['source_selection_status'] = 'original_sources_selected_capture_pending'
            selected['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                          'host_env_var': 'CARLA_HOST',
                                          'port_env_var': 'CARLA_PORT'}
            entries.append(selected)
            staged.extend(((source, construction), (measurement, contract),
                           (fallback_source, fallback)))
        manifest = {'format': 'worker-execution-manifest',
                    'assignment_id': HERE.name,
                    'status': 'original_sources_selected_capture_pending',
                    'runtime_manifest_sha256': sha(RUNTIME_MANIFEST),
                    'reviewed_site_packet_sha256': sha(packet_path),
                    'cases': entries}
        selection = {'format': 'c150153-original-source-selection',
                     'status': 'source_custody_only_capture_pending',
                     'reviewed_site_packet_sha256': sha(packet_path),
                     'external_source_hashes': {key: item['sha256']
                                                for key, item in packet['sources'].items()},
                     'runtime_manifest_sha256': sha(RUNTIME_MANIFEST),
                     'case_ids': [entry['case_id'] for entry in entries],
                     'physical_acceptance_claimed': False,
                     'legal_judgment': None}
        for source, target in staged:
            shutil.copy2(source, target)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        selected_path.write_text(json.dumps(selection, indent=2) + '\n')
        return selection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--body-length-m', type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(select(args.packet, args.source_root, args.body_length_m), indent=2))


if __name__ == '__main__':
    main()
