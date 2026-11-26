"""Reproduce one missing original overview source rejection in a scratch copy."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from independent_delivery_audit import audit

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / '.runtime-work/c150153-owner'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(dir=SCRATCH, prefix='deferred-delivery-negative-') as temp:
        missing = Path(temp) / 'attempt'
        shutil.copytree(args.attempt, missing, copy_function=os.link)
        (missing / 'overview.mkv').unlink()
        result = audit(missing, missing / 'reviewed-site/packet.json',
                       missing / 'reviewed-site/sources', diagnostic_fixture=True)
        if result['case_id'] != args.case:
            raise ValueError('negative delivery case identity differs')
        raise ValueError('missing original overview camera unexpectedly passed')


if __name__ == '__main__':
    main()
