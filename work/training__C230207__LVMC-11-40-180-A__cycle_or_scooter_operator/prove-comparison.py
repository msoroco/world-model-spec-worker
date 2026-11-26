"""Synthetic source fixtures exercise comparison invariants and rejections."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(audit, walk, ride, expected):
    try:
        audit(walk, ride)
    except ValueError as exc:
        if expected not in str(exc):
            raise
        return str(exc)
    raise AssertionError('invalid comparison source accepted')


def main():
    source = load('source_fixtures', 'prove-measure.py')
    audit = load('comparison_audit', 'comparison-audit.py').audit
    walk = source.fixture('comparison_walk', 'unverified', behavior='walk_cycle')
    ride = source.fixture('comparison_ride', 'unverified', behavior='mounted_sidewalk')
    passed = audit(walk, ride)
    assert passed['passed'] and not passed['physical_acceptance_claimed']
    context = json.loads(ride[1].read_text())
    context['sign_id'] = '101'
    bad_context = ride[1].parent / 'wrong-sign-context.json'
    bad_context.write_text(json.dumps(context) + '\n')
    wrong_sign = reject(audit, walk, (ride[0], bad_context, ride[2]),
                        'comparison fixed source condition differs')
    context = json.loads(walk[1].read_text())
    context['controlled_behavior'] = 'mounted_sidewalk'
    bad_context = walk[1].parent / 'wrong-behavior-context.json'
    bad_context.write_text(json.dumps(context) + '\n')
    wrong_behavior = reject(audit, (walk[0], bad_context, walk[2]), ride,
                            'comparison deliberate behavior source missing')
    rows = walk[0].read_text().splitlines()
    rows[0] = json.dumps({key: value for key, value in json.loads(rows[0]).items()
                          if key != 'operator_xy_m'})
    bad_pose = walk[0].parent / 'missing-operator-pose.jsonl'
    bad_pose.write_text('\n'.join(rows) + '\n')
    missing_operator = reject(audit, (bad_pose, walk[1], walk[2]), ride,
                              'original dismounted operator pose source missing')
    return {'passed': True, 'fixture_kind': 'synthetic_native_sample',
            'source_pre_audit': passed, 'negative_wrong_sign': wrong_sign,
            'negative_wrong_behavior': wrong_behavior,
            'negative_missing_operator': missing_operator}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
