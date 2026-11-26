"""Full-decode synthetic delivery protocol and absent-source rejection for 12 cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from independent_delivery_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.runtime-work/c150153-owner'
MANIFEST = HERE / 'execution-manifest.source-bound-diagnostic.json'
REPLAYED = {'front_park', 'front_stop', 'front_stand', 'west_inside'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt_for(kind: str) -> Path:
    suffix = '-bound' if kind in REPLAYED else ''
    return BASE / ('saved-source-' + kind.replace('_', '-') + suffix)


def prove() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest['status'] != 'synthetic_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('Original production manifest cannot use diagnostic delivery proof')
    rows = []
    for entry in manifest['cases']:
        kind = entry['case_id'].removeprefix(HERE.name + '__')
        attempt = attempt_for(kind)
        packet = attempt / 'reviewed-site/packet.json'
        sources = attempt / 'reviewed-site/sources'
        positive = audit(attempt, packet, sources, diagnostic_fixture=True)
        if (positive['case_id'] != entry['case_id'] or positive['frame_count'] != 900 or
                positive['camera_count'] != 4 or positive['full_video_decode'] is not True or
                positive['physical_acceptance_claimed'] is not False or
                positive['legal_judgment'] is not None):
            raise ValueError('Incomplete synthetic delivery protocol: ' + kind)
        rejected = []
        for missing in ('history.jsonl', 'overview.mkv'):
            with TemporaryDirectory(dir=BASE, prefix='delivery-negative-') as temp:
                negative = Path(temp) / 'attempt'
                shutil.copytree(attempt, negative, copy_function=os.link)
                (negative / missing).unlink()
                try:
                    audit(negative, negative / 'reviewed-site/packet.json',
                          negative / 'reviewed-site/sources', diagnostic_fixture=True)
                except ValueError as error:
                    message = str(error)
                    if 'sealed original source missing or changed: ' + missing not in message:
                        raise ValueError('Wrong source rejection: ' + message) from error
                    rejected.append({'missing': missing, 'error': message})
                else:
                    raise ValueError('Missing source passed diagnostic delivery: ' + missing)
        receipt = {'format': 'c150153-diagnostic-delivery',
                   'case_id': entry['case_id'],
                   'manifest_sha256': sha(MANIFEST),
                   'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
                   'reviewed_packet_sha256': sha(packet),
                   'positive': positive, 'negative': rejected,
                   'scope': 'synthetic protocol only',
                   'physical_acceptance_claimed': False}
        path = HERE / ('cpu-delivery-' + kind + '.json')
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        rows.append({'case_id': entry['case_id'], 'receipt': path.name,
                     'sha256': sha(path)})
        print(kind, 'full decode and two missing sources passed', flush=True)
    index = {'format': 'c150153-diagnostic-delivery-index',
             'status': 'synthetic_diagnostic_only',
             'manifest_sha256': sha(MANIFEST), 'cases': rows}
    (HERE / 'diagnostic-delivery-index.json').write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    prove()
