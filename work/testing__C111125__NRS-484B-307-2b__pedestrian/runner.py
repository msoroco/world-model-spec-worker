"""Source-honest diagnostic bundle precheck for C111125 pedestrian cases.

Native dispatch needs a reviewed site and a CARLA-facing adapter. The offline
precheck deliberately validates only the materialized exact case contract.
"""
import argparse
import json
from pathlib import Path


ASSIGNMENT = 'testing__C111125__NRS-484B-307-2b__pedestrian'
SUFFIXES = {'marked_cross', 'unmarked_cross', 'other_device_stop',
            'other_device_cross', 'outside_cross'}


def check(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'scene.json').read_text())
    suffix = scene.get('case_suffix')
    if suffix not in SUFFIXES or scene.get('case_id') != ASSIGNMENT + '__' + suffix:
        raise ValueError('exact pedestrian case identity mismatch')
    if config.get('selected_case_id') != scene['case_id'] or config.get('case') != scene:
        raise ValueError('materialized config and scene differ')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('20 Hz, 45 second capture required')
    if scene.get('diagnostic_only') is not True or config.get('source_packets') != []:
        raise ValueError('diagnostic bundle cannot assert reviewed site sources')
    if scene.get('requested_crossing') != (suffix != 'other_device_stop'):
        raise ValueError('requested crossing differs from exact case')
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', default='.')
    args = parser.parse_args()
    scene = check(args.output_dir)
    if not args.check:
        raise ValueError('reviewed Native site and CARLA adapter not bundled in diagnostic candidate')
    print(json.dumps({'case_id': scene['case_id'], 'diagnostic_precheck': 'passed'}))


if __name__ == '__main__':
    main()
