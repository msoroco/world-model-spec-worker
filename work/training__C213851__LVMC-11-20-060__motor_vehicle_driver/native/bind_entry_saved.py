"""Bind exact diagnostic saved-only receipts for roadway-return cases."""

import hashlib
import json
import shutil
from pathlib import Path

from build_entry_return import AID, POLICIES, ROOT


REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    cases = []
    for policy in POLICIES:
        folder = ROOT / 'native/entry_return' / policy / 'saved-proof'
        folder.mkdir(parents=True, exist_ok=True)
        rows = {}
        for variant in ('positive', 'negative'):
            path = (REPO / '.runtime-work' /
                    f'c213851-entry-saved-{variant}-{policy}-caseconfig' /
                    'v0001/processing.json')
            receipt = json.loads(path.read_text())
            missing = variant == 'negative'
            if (receipt.get('case_id') != AID + '__' + policy or
                    receipt.get('passed') is not True or
                    receipt.get('recorded_only') is not True or
                    receipt.get('originals_preserved') is not True or
                    receipt.get('missing_evidence') is not missing or
                    receipt.get('physical_acceptance_claimed') is not False or
                    receipt.get('legal_acceptance_claimed') is not False or
                    receipt.get('timestamp_joins', {}).get('frames') != 1200 or
                    receipt.get('timestamp_joins', {}).get('passed') is not True or
                    receipt.get('final_video_checks', {}).get('passed') is not True):
                raise ValueError('Incomplete saved-only receipt: ' +
                                 policy + '/' + variant)
            target = folder / (variant + '-processing.json')
            shutil.copyfile(path, target)
            log = folder / (variant + '-saved.log')
            log.write_text('recorded_only=true\nmissing_evidence=' +
                           str(missing).lower() +
                           '\noriginals_preserved=true\n')
            rows[variant] = {
                'receipt': target.relative_to(ROOT).as_posix(),
                'sha256': sha(target),
                'log': log.relative_to(ROOT).as_posix(),
                'log_sha256': sha(log),
                'missing_evidence': missing,
            }
        cases.append({'case_id': AID + '__' + policy,
                      'construction_sha256': sha(ROOT / 'native/entry_return' /
                                                 policy / 'construction.json'),
                      'positive': rows['positive'],
                      'negative': rows['negative']})
    proof = {'format': 'c213851-entry-saved-only-cpu-proof',
             'source_kind': 'synthetic_diagnostic',
             'cases': cases, 'positive_count': 2,
             'missing_source_negative_count': 2,
             'original_native_observed': False,
             'physical_acceptance_claimed': False,
             'legal_acceptance_claimed': False}
    path = ROOT / 'native/entry_return/saved-only-cpu-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'proof': path.relative_to(ROOT).as_posix(),
            'sha256': sha(path), 'cases': 2}


if __name__ == '__main__':
    print(json.dumps(bind()))
