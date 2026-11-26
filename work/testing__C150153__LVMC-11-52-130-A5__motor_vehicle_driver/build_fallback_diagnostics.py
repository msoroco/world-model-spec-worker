"""Stage a separate exact synthetic manifest for current source-bound fallback proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from build_source_bound_bundles import generate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / 'execution-manifest.fallback-diagnostic.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    if OUTPUT.exists():
        raise ValueError('refusing to overwrite fallback diagnostic manifest')
    source = json.loads((HERE / 'execution-manifest.source-bound-diagnostic.json').read_text())
    if source['status'] != 'synthetic_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('fallback diagnostics require unselected synthetic sources')
    scratch = ROOT / '.runtime-work/c150153-owner/fallback-diagnostic-build'
    scratch.mkdir(parents=True, exist_ok=True)
    entries = []
    for old in source['cases']:
        case_id = old['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        folder = HERE / 'cases' / kind
        packet = folder / 'fixture-sources/reviewed-site/packet.json'
        roots = folder / 'fixture-sources/reviewed-site/sources'
        output = scratch / kind
        if output.exists():
            raise ValueError('fresh fallback diagnostic draft path required: ' + kind)
        draft = generate(packet, roots, 4.0, output)
        entry = next(item for item in draft['cases'] if item['case_id'] == case_id)
        primary = folder / 'fallback-diagnostic-primary.json'
        fallback = folder / 'fallback-diagnostic-fallback1.json'
        if primary.exists() or fallback.exists():
            raise ValueError('refusing to overwrite diagnostic fallback construction')
        shutil.copy2(output / entry['construction'], primary)
        shutil.copy2(output / entry['candidates'][0]['construction'], fallback)
        if (sha(primary) != entry['construction_sha256'] or
                sha(fallback) != entry['candidates'][0]['construction_sha256']):
            raise ValueError('source-bound fallback construction changed: ' + kind)
        entry['construction'] = str(primary.relative_to(HERE))
        entry['candidates'][0]['construction'] = str(fallback.relative_to(HERE))
        entry['measurement_contract'] = old['measurement_contract']
        entry['fixture_recipe'] = old['fixture_recipe']
        entry['diagnostic_only'] = True
        entries.append(entry)
        print(kind, 'primary and fallback1 staged', flush=True)
    manifest = {'assignment_id': HERE.name,
                'status': 'synthetic_fallback_diagnostic_only_unselected_original_capture_pending',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    OUTPUT.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
