"""Reopen four synthetic source-shaped attempts and three comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from saved_process import process
from delivery_audit import audit as audit_delivery
from comparison_audit import audit_saved_pair

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ('adjacent_no_diagonal_authority', 'diagonal_no_authority',
            'diagonal_authorized', 'adjacent_authorized_device')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def build():
    attempts = {}
    for suffix in SUFFIXES:
        case_id = HERE.name + '__' + suffix
        original = REPO / '.runtime-work' / 'c111329-diagnostic' / suffix
        attempt = REPO / '.runtime-work' / 'c111329-independent-diagnostic' / suffix
        if attempt.exists():
            raise ValueError('retain earlier diagnostic attempt; use clean scratch')
        shutil.copytree(original, attempt)
        sources = HERE / 'cases' / suffix / 'diagnostic-sources'
        refs = []
        for name in ('site.json', 'native-acquisition.json', 'camera-manifest.json'):
            shutil.copy2(sources / name, attempt / name)
            refs.append({'path': name, 'sha256': sha(attempt / name)})
        receipt_path = attempt / 'saved-receipt.json'
        process(attempt, *refs, case_id, receipt_path,
                expected_frames=3, allow_diagnostic=True)
        refs.append({'path': 'saved-receipt.json', 'sha256': sha(receipt_path)})
        positive = audit_delivery(attempt, case_id, *refs,
                                  expected_frames=3, allow_diagnostic=True)
        if positive['diagnostic'] is not True:
            raise ValueError('synthetic delivery lost diagnostic provenance')
        write(HERE / 'cases' / suffix / 'independent-delivery-diagnostic.json', positive)
        attempts[suffix] = (attempt, refs)
        print('positive delivery', suffix, positive['decoded_png_count'])
    comparisons = {
        'diagonal_path_without_authority': ('adjacent_no_diagonal_authority', 'diagonal_no_authority'),
        'diagonal_device_authority': ('diagonal_no_authority', 'diagonal_authorized'),
        'authorized_device_path_control': ('diagonal_authorized', 'adjacent_authorized_device'),
    }
    for label, (left, right) in comparisons.items():
        receipt = audit_saved_pair(*attempts[left], *attempts[right], label,
                                   expected_frames=3, allow_diagnostic=True)
        write(HERE / 'comparisons' / (label + '.diagnostic.json'), receipt)
        print('positive comparison', label)
    for suffix in SUFFIXES:
        attempt, refs = attempts[suffix]
        source = attempt / 'overview' / '000000.png'
        source.write_bytes(source.read_bytes() + b'changed')
        try:
            audit_delivery(attempt, HERE.name + '__' + suffix, *refs,
                           expected_frames=3, allow_diagnostic=True)
        except ValueError as error:
            if 'hash mismatch' not in str(error):
                raise
            print('negative pixel-source audit', suffix, str(error))
        else:
            raise ValueError('tampered original PNG passed independent delivery')


if __name__ == '__main__':
    build()
