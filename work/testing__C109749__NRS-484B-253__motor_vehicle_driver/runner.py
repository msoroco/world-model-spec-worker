"""Materialize one exact C109749 candidate for local Native execution."""
import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args(argv)
    manifest = Path(__file__).with_name('execution-manifest.json')
    command = [sys.executable, 'runtime.py', 'materialize', '--manifest', str(manifest),
               '--case', args.case, '--candidate', args.candidate, '--output', args.output]
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
