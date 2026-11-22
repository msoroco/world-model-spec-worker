"""Return bounded receipts from the two early cutover reference probes."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / '.runtime-work/c183370-cutover-probe'
MANIFEST = HERE / 'current-runtime-probe-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    case = manifest['cases'][0]
    for candidate, compat, source, saved in (
            ('primary', ASSETS / 'compat', ASSETS / 'source', ASSETS / 'saved2'),
            ('fallback1', ASSETS / 'compat-fallback1', ASSETS / 'source-fallback1', ASSETS / 'saved-fallback1')):
        selected = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
        dest = HERE / 'cutover-receipts/reference' / candidate
        dest.mkdir(parents=True, exist_ok=True)
        files = {'compatibility.json': compat / 'compatibility.json',
                 'compatibility-analysis.log': compat / 'compatibility-analysis.log',
                 'negative-analysis.log': compat / 'negative-analysis.log',
                 'processing.json': saved / 'v0001/processing.json'}
        hashes = {}
        for name, src in files.items():
            dst = dest / name
            if not dst.exists():
                shutil.copyfile(src, dst)
            if sha(dst) != sha(src) or dst.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Returned receipt mismatch: ' + name)
            hashes[name] = sha(dst)
        selection = json.loads((source / 'candidate-selection.json').read_text())
        comp = json.loads((compat / 'compatibility.json').read_text())
        proc = json.loads((saved / 'v0001/processing.json').read_text())
        if not (selection['manifest_sha256'] == sha(MANIFEST) and
                selection['construction_sha256'] == comp['construction_sha256'] ==
                proc['analysis_revision']['construction_sha256'] == selected['construction_sha256'] and
                comp['passed'] and comp['negative_error_contains'] == 'Missing required source: live-readback.json' and
                proc['passed'] and proc['recorded_only'] and proc['originals_preserved'] and
                not proc['missing_evidence'] and proc['timestamp_joins']['frames'] == 600):
            raise ValueError('Early exact chain is incomplete')
        proof = {'format': 'current-runtime-exact-candidate-cpu-proof',
                 'status': 'probe_only_selected_manifest_unchanged',
                 'case_id': case['case_id'], 'candidate_id': candidate,
                 'manifest_sha256': sha(MANIFEST),
                 'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                 'construction_sha256': selected['construction_sha256'],
                 'selection_sha256': sha(source / 'candidate-selection.json'),
                 'returned_receipts': hashes,
                 'positive_compatibility_passed': True,
                 'missing_source_negative_passed': True,
                 'recorded_only_saved_passed': True,
                 'source_frames': 600, 'synthetic_fixture': True,
                 'original_native_verified': False,
                 'physical_or_legal_acceptance_claimed': False}
        path = dest / 'proof.json'
        path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'candidate': candidate, 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
