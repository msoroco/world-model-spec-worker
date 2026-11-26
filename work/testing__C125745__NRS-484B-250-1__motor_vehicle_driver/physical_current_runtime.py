"""Run physical CPU fixtures against the renewed execution manifest."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'physical_motion_fixture.py'
PROOF = HERE / 'execution-manifest-current-runtime-proof.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion',
                                 'missing_evidence', 'lifecycle'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('physical_motion_fixture', SOURCE)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    original_read = fixture.read

    def read(path):
        if Path(path).resolve() == HERE / 'execution-manifest.json':
            return json.loads(PROOF.read_text())
        return original_read(path)

    fixture.read = read
    result = fixture.run(args.case, args.kind, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
