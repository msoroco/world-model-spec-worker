"""Exact right-pass Native entrypoint; --check imports no CARLA."""
import argparse
from pathlib import Path
import subprocess
import sys


def command(bundle,output=None,host=None,port=None,check=False):
    bundle=Path(bundle).resolve()
    source=bundle/'capture.py'
    if not source.is_file():raise ValueError('Exact capture implementation missing')
    args=[sys.executable,str(source),'--bundle',str(bundle)]
    if check:args.append('--check')
    else:
        if output is None or host is None or port is None:
            raise ValueError('Native capture needs output, host and port')
        args+=['--output-dir',str(Path(output).resolve()),
               '--host',str(host),'--port',str(port)]
    return args


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port',type=int)
    a=parser.parse_args()
    bundle=Path(__file__).resolve().parent
    subprocess.run(command(bundle,a.output_dir,a.host,a.port,a.check),
                   cwd=bundle,check=True)
