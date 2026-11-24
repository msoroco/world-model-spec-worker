"""Collect compact current-runtime 140(B) CPU receipts from scratch outputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip() + '\n')
    return digest(target)


def main():
    manifest = json.loads((HERE / 'crossref-140b-manifest.json').read_text())
    records = []
    for entry in manifest['cases']:
        label = entry['case_id'].split('__crossref_lvmc_11_30_140_b_', 1)[1]
        variants = {}
        for candidate, local in (('primary', HERE / 'crossref-140b-native' / label),
                                 ('fallback1', HERE / 'crossref-140b-fallback1' / label)):
            stem = 'c230222-crossref-140b-' + label
            if candidate == 'fallback1':
                offline = SCRATCH / (stem + '-fallback-offline1') / 'offline.log'
                compat = SCRATCH / (stem + '-fallback-compat2')
                saved = SCRATCH / (stem + '-fallback-saved2') / 'v0001'
            else:
                offline = SCRATCH / (stem + '-offline1') / 'offline.log'
                compat = SCRATCH / (stem + '-compat2')
                saved = SCRATCH / (stem + '-saved2') / 'v0001'
            sources = {
                'offline.log': offline,
                'compatibility.json': compat / 'compatibility.json',
                'positive-analysis.log': compat / 'compatibility-analysis.log',
                'negative-analysis.log': compat / 'negative-analysis.log',
                'processing.json': saved / 'processing.json',
                'saved-analysis.log': saved / 'analysis.log'}
            hashes = {name: copy_text(source, local / 'proofs' / name)
                      for name, source in sources.items()}
            assert json.loads((local / 'proofs/compatibility.json').read_text())['passed'] is True
            processing = json.loads((local / 'proofs/processing.json').read_text())
            assert processing['passed'] is True and processing['recorded_only'] is True
            variants[candidate] = hashes
        records.append({'case_id': entry['case_id'],
                        'construction_sha256': digest(HERE / entry['construction']),
                        'cane_prop_requested': entry['cane_prop_requested'],
                        'current_runtime_proof_hashes': variants})
    output = {'format': 'c230222-140b-cane-prop-survey-cpu-proof-v1',
              'records': records, 'public_positive_count': 4,
              'missing_source_negative_count': 4,
              'recorded_only_saved_count': 4,
              'native_prop_available_verified': False,
              'original_cane_pixels_verified': False,
              'pedestrian_blindness_verified': False,
              'driver_precautions_reviewed': False,
              'legal_applicability_conclusion': None}
    target = HERE / 'crossref-140b-native/proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'proof_sha256': digest(target), 'records': len(records)}))


if __name__ == '__main__':
    main()
