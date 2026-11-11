"""Portable entrypoint for the exact C132497 primary right-exit bundle.

The pinned runtime materializes this file alongside capture.py and check.py.
No CARLA import or server contact occurs during --check.
"""
import argparse
from pathlib import Path
import subprocess
import sys


def command(bundle, output=None, host=None, port=None, check=False):
    bundle = Path(bundle).resolve()
    if not (bundle/'capture.py').is_file():
        raise ValueError('C132497 Native capture implementation missing')
    args = [sys.executable, str(bundle/'capture.py'), '--bundle', str(bundle)]
    if check:
        args.append('--check')
    else:
        if output is None or host is None or port is None:
            raise ValueError('Native capture requires output, host and port')
        args += ['--output-dir', str(Path(output).resolve()), '--host', host,
                 '--port', str(port)]
    return args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    subprocess.run(command(bundle, args.output_dir, args.host, args.port,
                           args.check), check=True, cwd=bundle)


if __name__ == '__main__':
    main()
