"""Embed the current four-camera Native capture in exact case constructions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAPTURE = (HERE / 'native/zone/capture-current.py').read_text()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


for suffix in ('condition_a', 'condition_b'):
    primary_path = None
    for candidate in ('primary', 'fallback1', 'fallback2'):
        tag = suffix if candidate == 'primary' else f'{suffix}-{candidate}'
        source = HERE / f'current-runtime-v2-{tag}-construction.json'
        construction = json.loads(source.read_text())
        capture = next(item for item in construction['files'] if item['path'] == 'capture.py')
        capture['content'] = CAPTURE
        construction['status'] = 'selected_source_candidate_pending_cpu_proofs'
        output = HERE / f'selected-current-v2-{tag}-construction.json'
        save(output, construction)
        if candidate == 'primary':
            primary_path = output

        diagnostic = json.loads((HERE / f'current-runtime-v2-{tag}-probe-manifest.json').read_text())
        entry = diagnostic['cases'][0]
        entry['construction'] = primary_path.name
        entry['construction_sha256'] = sha(primary_path)
        if candidate != 'primary':
            fallback = entry['candidates'][0]
            fallback['construction'] = output.name
            fallback['construction_sha256'] = sha(output)
        diagnostic['format'] = 'worker-selected-source-probe-manifest'
        diagnostic['status'] = 'selected_source_pending_delivery_proofs'
        probe = HERE / f'selected-current-v2-{tag}-probe-manifest.json'
        save(probe, diagnostic)
        print(json.dumps({'tag': tag, 'construction_sha256': sha(output),
                          'probe_manifest_sha256': sha(probe)}))
