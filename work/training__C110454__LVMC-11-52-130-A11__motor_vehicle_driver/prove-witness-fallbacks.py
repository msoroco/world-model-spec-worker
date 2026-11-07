"""Build source-shaped CPU trigger contrasts for the intersection parking pair."""
import hashlib
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--numeric', action='store_true')
    parser.add_argument('--exceptions', action='store_true')
    args = parser.parse_args()
    assert not (args.numeric and args.exceptions)
    cases = (tuple('exception_'+str(branch)+'_'+str(polarity)
                   for branch in (1,2,3) for polarity in (1,2)) if args.exceptions else
             ('numeric_1_0','numeric_1_1','numeric_1_2') if args.numeric else
             ('witness_1','witness_2'))
    output = HERE / ('exception-fallback-source.json' if args.exceptions else
                     'numeric-fallback-source.json' if args.numeric else 'witness-fallback-source.json')
    entries = {}
    for case in cases:
        source = (HERE/'exception-polarity-sources'/case/'exception_context.json'
                  if args.exceptions else ROOT/'.runtime-work/c110454-lvmc-synthetic'/(case+'-native.json'))
        packet = json.loads(source.read_text())
        if args.exceptions:
            assert packet['synthetic_diagnostic'] is True and len(packet['original_frames']) == 480
        else:
            assert packet['synthetic_fixture'] is True and len(packet['frames']) == 480
        route = json.loads((HERE / 'native/routes' / (case + '.json')).read_text())
        assert len(route) > 400
        entries[case] = {('context_source_sha256' if args.exceptions else 'saved_source_sha256'): sha(source),
                         'route_sha256': sha(HERE / 'native/routes' / (case + '.json')),
                         'scenarios': {}}
        for scenario in ('baseline', 'route_error', 'endpoint_speed', 'pixel_margin'):
            samples = []
            for i in range(480):
                target_x, target_y = route[min(round(i*(len(route)-1)/399),len(route)-1)]
                if args.exceptions:
                    center_x, center_y = target_x, target_y
                else:
                    body = packet['frames'][i]['body_xy_m']
                    center_x = sum(point[0] for point in body) / 4
                    center_y = sum(point[1] for point in body) / 4
                if scenario == 'route_error' and 300 <= i < 390:
                    center_y += .60
                speed = (4.0 if i < 400 else 0.0) if args.exceptions else packet['frames'][i]['speed_m_s']
                if scenario == 'endpoint_speed' and i >= 400:
                    speed = .60
                # Synthetic projection box; original pixels must replace this on GPU.
                box = [10, 420, 300, 650] if scenario == 'pixel_margin' and i >= 400 else [800, 420, 1100, 650]
                samples.append({'frame': i, 'route_error_m': round(((center_x-target_x)**2+(center_y-target_y)**2)**.5, 6),
                                'speed_m_s': speed, 'overview_body_bbox_px': box})
            entries[case]['scenarios'][scenario] = samples
    output.write_text(json.dumps({'format':'c110454-parking-trigger-source-v1',
                                  'source_kind':'synthetic_cpu', 'cases':entries}, separators=(',',':'))+'\n')
    print(sha(output))


if __name__ == '__main__':
    main()
