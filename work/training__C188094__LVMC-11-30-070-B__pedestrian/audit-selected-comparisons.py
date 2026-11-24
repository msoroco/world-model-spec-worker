"""Run the three-case independent comparison and an original-road tamper check."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
MODULE = HERE / 'audit-v2-common-intersection.py'
spec = importlib.util.spec_from_file_location('common_intersection_audit', MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def run(attempts, saved, reject_road_drift=False):
    if reject_road_drift:
        scratch = Path('.runtime-work').resolve()
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c188094-comparison-negative-') as name:
            replacement = Path(name)
            for source in attempts[2].iterdir():
                if source.name == 'road.xodr':
                    replacement.joinpath(source.name).write_bytes(source.read_bytes() + b'\n<!-- tampered -->\n')
                else:
                    replacement.joinpath(source.name).symlink_to(source.resolve(),
                                                                 target_is_directory=source.is_dir())
            try:
                audit_module.audit({**attempts, 2: replacement}, saved)
            except ValueError as error:
                if 'original source changed: road.xodr' not in str(error):
                    raise
                raise ValueError('Comparison fixed road source changed') from error
            raise ValueError('Comparison audit accepted a tampered road source')
    result = audit_module.audit(attempts, saved)
    if result['passed'] is not True or len(result['case_receipt_hashes']) != 3:
        raise ValueError('Three-case comparison proof incomplete')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for number in (1, 2, 3):
        parser.add_argument(f'--attempt{number}', type=Path, required=True)
        parser.add_argument(f'--saved{number}', type=Path, required=True)
    parser.add_argument('--reject-road-drift', action='store_true')
    args = parser.parse_args()
    attempts = {n: getattr(args, f'attempt{n}') for n in (1, 2, 3)}
    saved = {n: getattr(args, f'saved{n}') for n in (1, 2, 3)}
    print(json.dumps(run(attempts, saved, args.reject_road_drift)))
