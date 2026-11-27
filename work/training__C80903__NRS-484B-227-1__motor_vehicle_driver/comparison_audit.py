"""Independent authored and source-fact isolation for C80903 left-turn pairs."""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAIRS = {'opening_vs_section': ('opening_left', 'section_left', {'crossing_mode', 'requested_crossing_station_m'}),
         'crossover_authority': ('crossover_established', 'crossover_unestablished', {'crossing_mode'}),
         'roadway_duty': ('roadway_right', 'roadway_opposite', {'requested_initial_roadway'})}
KEYS = ('actor', 'cell_id', 'law_id', 'duration_s', 'frames', 'rate_hz', 'cameras',
        'requested_turn_mode', 'crossing_mode', 'requested_crossing_station_m',
        'requested_initial_roadway')


def configs(pair):
    result = []
    for suffix in PAIRS[pair][:2]:
        path = ROOT / 'native' / ('config.json' if suffix == 'opening_left' else 'cases/' + suffix + '/config.json')
        result.append(json.loads(path.read_text()))
    return result


def verify(pair, values, reports):
    left, right = values
    changed = {key for key in KEYS if left.get(key) != right.get(key)}
    if changed != PAIRS[pair][2]:
        raise ValueError('Uncontrolled authored comparison: ' + str(sorted(changed)))
    if any(item.get('requested_turn_mode') != 'left_turn' or item.get('frames') != 600 or item.get('rate_hz') != 20 for item in values):
        raise ValueError('Frozen left-turn or capture contract differs')
    if reports:
        a, b = [r['measurements']['crossing_section']['value'] for r in reports]
        if any(v.get('frame_count') != 600 or v.get('observed_left_turn') is not True for v in (a, b)):
            raise ValueError('Observed comparison source missing')
        if pair == 'opening_vs_section' and not (a['median_overlap_frames_outside_authorized_opening'] == 0 < b['median_overlap_frames_outside_authorized_opening']):
            raise ValueError('Opening versus section source fact not isolated')
        if pair == 'crossover_authority' and (a['public_authority_crossover_established'], b['public_authority_crossover_established']) != (True, False):
            raise ValueError('Original public-authority source contrast missing')
        if pair == 'roadway_duty' and not (a['wrong_roadway_frame_count'] != b['wrong_roadway_frame_count']):
            raise ValueError('Original roadway occupancy contrast missing')
    return True


def selftest(pair, negative):
    values = configs(pair)
    if negative:
        values = copy.deepcopy(values)
        values[1]['duration_s'] += 1
    verify(pair, values, None)
    print(json.dumps({'comparison': pair, 'cpu_authored_isolation_passed': True,
                      'original_source_claimed': False}))


def audit(pair, attempts):
    if len(attempts) != 2:
        raise ValueError('Two exact original attempts required')
    reports = []
    for suffix, folder in zip(PAIRS[pair][:2], attempts):
        folder = Path(folder)
        result = json.loads((folder / 'result.json').read_text())
        if result.get('case_id') != ROOT.name + '__' + suffix or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
            raise ValueError('Original Native comparison source missing')
        reports.append(json.loads((folder / 'analysis-report.json').read_text()))
    verify(pair, configs(pair), reports)
    return {'comparison': pair, 'original_source_isolation_passed': True,
            'legal_compliance': 'unassessed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=PAIRS, required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt', action='append')
    args = parser.parse_args()
    if args.self_test:
        selftest(args.comparison, args.negative)
    else:
        print(json.dumps(audit(args.comparison, args.attempt or [])))
