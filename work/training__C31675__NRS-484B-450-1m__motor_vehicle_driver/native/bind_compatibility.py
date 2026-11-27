"""Bind selected public compatibility receipts without changing their scope."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
folder = here.parent
root = folder.parents[1]
manifest_path = folder / 'draft-execution-manifest.json'
manifest = json.loads(manifest_path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    edition = 'final9' if suffix == 'false' else 'final8'
    source = root / '.runtime-work' / ('c31675-public-' + suffix + '-primary-' + edition)
    receipt = json.loads((source / 'compatibility.json').read_text())
    if receipt.get('passed') is not True or receipt.get('case_id') != entry['case_id']:
        raise ValueError('Public compatibility did not pass exact case: ' + suffix)
    target = folder / 'proofs' / suffix
    target.mkdir(parents=True, exist_ok=True)
    for name, key in [('compatibility-analysis.log', 'log_sha256'),
                      ('negative-analysis.log', 'negative_log_sha256')]:
        path = target / ('primary-' + name)
        path.write_text((source / name).read_text().rstrip() + '\n')
        receipt[key] = digest(path)
    receipt_path = target / 'primary-compatibility.json'
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    entry['compatibility'] = {
        'receipt': str(receipt_path.relative_to(folder)), 'sha256': digest(receipt_path),
        'log': str((target / 'primary-compatibility-analysis.log').relative_to(folder)),
        'negative_log': str((target / 'primary-negative-analysis.log').relative_to(folder))}
    entry['negative'] = {
        'log': entry['compatibility']['negative_log'],
        'log_sha256': digest(target / 'primary-negative-analysis.log')}
    entry['acquisition'] = {
        name: {'entrypoint': 'finalize.py', 'method': 'finalize',
               'evidence': ['bridge-trace.jsonl', 'bridge-map.json',
                            'video_frames.jsonl', 'road.xodr']}
        for name in ('bridge_relation', 'speed_mps', 'stationary_candidate',
                     'halt_purpose_context', 'traffic_conflict_context',
                     'law_compliance_context', 'police_direction_context',
                     'device_direction_context', 'source_camera_frame_join')}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'public_compatibility_bound': len(manifest['cases'])}))
