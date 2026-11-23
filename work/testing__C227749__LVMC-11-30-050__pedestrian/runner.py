"""Exact pedestrian construction entrypoint; Native map binding remains pending."""
import argparse
import json
from pathlib import Path
from crossing_geometry import validate_scene


def check_bundle(root):
    scene=json.loads((root/'scene.json').read_text())
    config=json.loads((root/'config.json').read_text())
    measured=validate_scene(scene)
    if config['selected_case_id'] != scene['case_id']:
        raise ValueError('exact case identity differs')
    if config['actor'] != 'pedestrian' or config['rate_hz'] != 20:
        raise ValueError('pedestrian and 20 Hz capture required')
    if [item['name'] for item in config['cameras']] != ['overview','approach','reference_corner','driver_reference']:
        raise ValueError('four exact cameras required')
    return {'case_id':scene['case_id'], 'authored_geometry_valid':True,
            'route_length_m':measured['route_length_m'], 'native_map_binding':'pending'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    args=parser.parse_args()
    if args.check:
        print(json.dumps(check_bundle(Path.cwd())))
    elif args.output_dir:
        raise RuntimeError('Native execution requires source-bound map and four-camera runner; package remains partial')
    else:
        parser.error('use --check or --output-dir')


if __name__=='__main__': main()
