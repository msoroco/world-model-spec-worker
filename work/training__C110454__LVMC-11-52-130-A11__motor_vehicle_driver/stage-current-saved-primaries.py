"""Retain source-bound recorded-only primary receipts from synthetic CPU fixtures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c110454-current-recorded-only'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = [HERE / 'current-v2-witness-fallback-manifest.json',
             HERE / 'current-profile-statutory-manifest.json']
    entries = [item for path in paths for item in json.loads(path.read_text())['cases']]
    summary = {'format': 'c110454-current-recorded-only-primaries-v1',
               'status': 'synthetic_cpu_diagnostic', 'native_executed': False,
               'physical_or_legal_acceptance_claimed': False, 'chains': []}
    for item in entries:
        suffix = item['case_id'].rsplit('__', 1)[-1]
        source = SCRATCH / suffix / 'primary/processed/v0001/processing.json'
        log = SCRATCH / suffix / 'primary/process-saved.log'
        proof = json.loads(source.read_text())
        assert proof['passed'] is True and proof['recorded_only'] is True
        assert proof['case_id'] == item['case_id']
        assert proof['native_revision']['construction_sha256'] == item['construction_sha256']
        dest = HERE / 'current-v3-saved-primaries' / suffix
        dest.mkdir(parents=True, exist_ok=True)
        receipt_target = dest / 'processing.json'
        receipt_target.write_bytes(source.read_bytes())
        record = {
            'case_id': item['case_id'], 'construction_sha256': item['construction_sha256'],
            'receipt': str(receipt_target.relative_to(HERE)), 'receipt_sha256': sha(receipt_target),
            'original_source_count': len(proof['original_source_hashes'])}
        if log.is_file():
            log_target = dest / 'process-saved.log'
            log_target.write_text(log.read_text().rstrip() + '\n')
            record['log'] = str(log_target.relative_to(HERE))
            record['log_sha256'] = sha(log_target)
        summary['chains'].append(record)
    out = HERE / 'current-v3-saved-primary-cpu-proof.json'
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'chains': len(summary['chains']), 'sha256': sha(out)}))


if __name__ == '__main__':
    main()
