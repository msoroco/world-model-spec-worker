"""Make missing-original and altered-source negative delivery audit fixtures."""
import argparse
from pathlib import Path
import shutil
import tempfile

from delivery_audit import check

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
NAMES = ('construction.json', 'native-index.json', 'geometry.json', 'signal.json',
         'native-rows.jsonl', 'trace.jsonl', 'video_frames.jsonl',
         'interaction_history.jsonl', 'acquisition-provenance.json')


def run(letter, case, mode):
    source = REPO / '.runtime-work' / f'c111277-compat-new-{letter}-primary'
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111277-delivery-negative-') as directory:
        stage = Path(directory)
        for name in NAMES:
            shutil.copy2(source / name, stage / name)
        (stage / 'capture').mkdir()
        shutil.copy2(source / 'capture/manifest.json', stage / 'capture/manifest.json')
        if mode == 'missing':
            (stage / 'native-rows.jsonl').unlink()
            expected = 'missing original: native-rows.jsonl'
        else:
            with (stage / 'native-rows.jsonl').open('a') as stream:
                stream.write('\n')
            expected = 'altered original: native-rows.jsonl'
        try:
            check(stage, case)
        except ValueError as error:
            if expected not in str(error):
                raise
            print(str(error))
            raise SystemExit(3)
        raise AssertionError('negative delivery source was accepted')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--letter', choices=['a', 'b'], required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--mode', choices=['missing', 'altered'], required=True)
    a = p.parse_args()
    run(a.letter, a.case, a.mode)
