"""Preserve recorded-only diagnostic receipts without claiming Native capture."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
SCRATCH = REPO / '.runtime-work'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    rows = []
    for suffix, short in [('stop_before_sidewalk', 'stop'),
                          ('cross_without_stop', 'cross')]:
        output = HERE / suffix / 'saved-proof'
        output.mkdir(parents=True, exist_ok=True)
        entries = {}
        for variant in ('positive', 'negative'):
            origin_name = f'c213851-saved-{short}'
            if variant == 'negative':
                origin_name += '-negative'
            origin = SCRATCH / (origin_name + '-output/v0001')
            source = origin / 'processing.json'
            receipt = json.loads(source.read_text())
            expected_missing = variant == 'negative'
            if (receipt.get('passed') is not True or
                    receipt.get('recorded_only') is not True or
                    receipt.get('originals_preserved') is not True or
                    receipt.get('missing_evidence') is not expected_missing or
                    receipt.get('physical_acceptance_claimed') is not False or
                    receipt.get('legal_acceptance_claimed') is not False or
                    receipt.get('timestamp_joins', {}).get('frames') != 600 or
                    receipt.get('timestamp_joins', {}).get('passed') is not True or
                    receipt.get('final_video_checks', {}).get('passed') is not True):
                raise ValueError('Recorded-only processing proof failed: ' +
                                 suffix + '/' + variant)
            target = output / (variant + '-processing.json')
            shutil.copyfile(source, target)
            if sha(target) != sha(source):
                raise ValueError('Copied receipt differs')
            log = output / (variant + '-saved.log')
            log.write_text('recorded_only=true\nmissing_evidence=' +
                           str(expected_missing).lower() +
                           '\noriginals_preserved=true\n')
            entries[variant] = {
                'receipt': target.relative_to(ROOT).as_posix(),
                'sha256': sha(target),
                'log': log.relative_to(ROOT).as_posix(),
                'log_sha256': sha(log),
                'missing_evidence': expected_missing,
                'source_sha256': sha(source),
            }
        rows.append({'case_id': ROOT.name + '__' + suffix,
                     'construction_sha256': sha(HERE / suffix /
                                                'construction.json'),
                     'positive': entries['positive'],
                     'negative': entries['negative']})
    proof = {'format': 'c213851-saved-only-cpu-proof',
             'source_kind': 'synthetic_diagnostic',
             'cases': rows,
             'positive_count': 2,
             'missing_source_negative_count': 2,
             'original_native_observed': False,
             'physical_acceptance_claimed': False,
             'legal_acceptance_claimed': False}
    path = HERE / 'saved-only-cpu-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'proof': path.relative_to(ROOT).as_posix(),
            'sha256': sha(path), 'cases': len(rows)}


if __name__ == '__main__':
    print(json.dumps(bind()))
