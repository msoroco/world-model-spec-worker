"""Retain small receipts from the current manifest's six CPU execution paths."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    value = source.read_text().rstrip() + '\n'
    target.write_text(value)


def collect(probe, candidate):
    stem = probe + '-' + candidate
    case = HERE.name + '__' + probe
    compat = ROOT / '.runtime-work/c10389-selected-compat' / stem
    saved = ROOT / '.runtime-work/c10389-selected-saved' / stem / 'v0001'
    output = HERE / 'selected-proof' / stem
    output.mkdir(parents=True, exist_ok=True)
    for filename, source in {
        'candidate-selection.json': compat / 'candidate-selection.json',
        'compatibility.json': compat / 'compatibility.json',
        'analysis.log': compat / 'compatibility-analysis.log',
        'negative-analysis.log': compat / 'negative-analysis.log',
        'processing.json': saved / 'processing.json',
        'saved-analysis.log': saved / 'analysis/compatibility-analysis.log',
    }.items():
        if not source.is_file():
            raise ValueError(f'Missing selected source: {stem}/{filename}')
        copy_text(source, output / filename)
    selection = json.loads((output / 'candidate-selection.json').read_text())
    proof = json.loads((output / 'compatibility.json').read_text())
    processing = json.loads((output / 'processing.json').read_text())
    if (selection['manifest_sha256'] != sha(MANIFEST)
            or selection['candidate_id'] != candidate
            or proof['case_id'] != case or proof['candidate_id'] != candidate
            or not proof['passed'] or not processing['passed']
            or not processing['recorded_only'] or not processing['originals_preserved']
            or processing['case_id'] != case or processing['candidate_id'] != candidate
            or processing.get('physical_acceptance_claimed')
            or processing.get('legal_acceptance_claimed')):
        raise ValueError(f'Selected CPU proof mismatched: {stem}')
    files = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    summary = {'format': 'c10389-selected-current-runtime-cpu-proof-v1',
               'case_id': case, 'candidate_id': candidate,
               'manifest_sha256': sha(MANIFEST),
               'construction_sha256': selection['construction_sha256'],
               'runtime_manifest_sha256': proof['runtime_manifest_sha256'],
               'checks': proof['checks'], 'recorded_only': True,
               'originals_preserved': True, 'frames': 600,
               'original_native_observed': False,
               'physical_acceptance_claimed': False,
               'legal_acceptance_claimed': False,
               'files': files}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(stem, sha(output / 'summary.json'))


for p in ['probe_1', 'probe_2']:
    for c in ['primary', 'fallback1', 'fallback2']:
        collect(p, c)
