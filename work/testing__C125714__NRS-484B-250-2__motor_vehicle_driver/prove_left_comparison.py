"""Run the source comparison and reject a changed crossing geometry source."""

import json
import shutil
import tempfile
from pathlib import Path

from comparison_audit import check

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RIGHT = REPO / '.runtime-work/c125714-right-three-compat-v1'
LEFT = REPO / '.runtime-work/c125714-left-three-compat-v1'


def main():
    result = check(RIGHT, LEFT)
    full = check(REPO / '.runtime-work/c125714-250-2-saved-full-duration-v1/positive',
                 REPO / '.runtime-work/c125714-left-full-duration-v1/positive',
                 expected_frames=1100)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c125714-left-negative-') as temp:
        path = Path(temp)
        for name in ('config.json', 'road_geometry.json', 'crossing_history.jsonl',
                     'video_frames.jsonl', 'controller_history.jsonl', 'trace.jsonl',
                     'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                     'driver_reference.mkv'):
            shutil.copyfile(LEFT / name, path / name)
        geometry = json.loads((path / 'road_geometry.json').read_text())
        geometry['intersection_id'] = 999
        (path / 'road_geometry.json').write_text(json.dumps(geometry) + '\n')
        try:
            check(RIGHT, path)
        except ValueError as error:
            if 'Fixed crossing geometry changed: intersection_id' not in str(error):
                raise
            negative = str(error)
        else:
            raise AssertionError('Changed crossing identity passed comparison')
    output = ROOT / 'cases/source_verified_other_left_near_time/comparison-receipt.json'
    output.write_text(json.dumps({'short_fixture': result, 'full_duration_fixture': full,
                                  'negative_rejected': negative}, indent=2) + '\n')
    print(json.dumps({'comparison': 'right_vs_left_approach',
                      'entry_delta_s': result['entry_delta_s'],
                      'other_right_by_case': result['other_right_by_case'],
                      'full_duration_frames': full['frames'],
                      'full_duration_entry_delta_s': full['entry_delta_s'],
                      'negative_rejected': negative,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
