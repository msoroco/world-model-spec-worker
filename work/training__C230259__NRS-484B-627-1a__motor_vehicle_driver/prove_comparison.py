"""CPU positive and negative tests of independent paired source comparison."""
import copy
import json

from audit_comparison import compare, load
from prove_slow_traffic_measure import SCRATCH, fixture


def write(name, right):
    sources = fixture(name, right)
    folder = SCRATCH / name
    for filename, content in zip(('slow-traffic-trace.jsonl', 'video_frames.jsonl',
                                  'slow-traffic-context.json', 'road.xodr'), sources):
        (folder / filename).write_bytes(content)
    return folder


def reject(a, b, expected):
    try:
        compare(a, b)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Comparison accepted changed fixed source')


def main():
    right, away = write('comparison-right', True), write('comparison-away', False)
    a, b = load(right), load(away)
    report = compare(a, b)
    reversed_rejection = reject(b, a, 'rightward versus lane-center contrast absent')
    altered = copy.deepcopy(b)
    altered['rows'][20]['follower_free_flow_request_mps'] = 7
    policy_rejection = reject(a, altered, 'fixed policy or time differs')
    altered = copy.deepcopy(b)
    context = json.loads(altered['raw'][2])
    context['paved_width_m'] = 8
    altered['raw'][2] = json.dumps(context).encode()
    highway_rejection = reject(a, altered, 'highway context differs')
    print(json.dumps({'passed': True, 'positive': report,
                      'negative_reversed': reversed_rejection,
                      'negative_policy': policy_rejection,
                      'negative_highway': highway_rejection}, sort_keys=True))


if __name__ == '__main__':
    main()
