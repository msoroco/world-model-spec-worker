"""Unselected synthetic steady-indication witness pair and adversarial sources."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / 'work/training__C10316__NRS-484B-283-1d3__pedestrian'
source_summary = json.loads((PARENT / 'no-countdown-summary.json').read_text())
SOURCE = Path(source_summary['records'][0]['retained_positive'])
sys.path.insert(0, str(HERE / 'native'))
from steady import measure, sha


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def main():
    if not SOURCE.is_dir():
        raise RuntimeError('Retained synthetic pedestrian path missing')
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-steady-'))
    base = [json.loads(line) for line in (SOURCE / 'no-countdown-samples.jsonl').read_text().splitlines()]
    context_base = json.loads((SOURCE / 'no-countdown-context.json').read_text())
    assert len(base) == 240
    records = []
    for suffix, steady_start, expected in (
        ('witness_1', 4.0, 'before_steady'),
        ('witness_2', .5, 'at_or_after_steady'),
    ):
        folder = root / suffix
        folder.mkdir()
        shutil.copy2(PARENT / 'native/road.xodr', folder / 'road.xodr')
        context = dict(context_base)
        context.update(authored_map_sha256=sha(folder / 'road.xodr'),
                       source_kind='synthetic_scene_request', steady_start_s=steady_start,
                       lawful_prior_entry_review='unverified',
                       introductory_exceptions='unreviewed_synthetic_context',
                       safety_destination_review='unverified',
                       as_soon_as_possible_judgment_bound=None)
        (folder / 'steady-context.json').write_text(json.dumps(context, indent=2) + '\n')
        values = []
        for index, original in enumerate(base):
            row = {key: value for key, value in original.items() if key not in
                   ('indication', 'display_illuminated', 'countdown_visible')}
            row.update(indication='walk' if index / 20 < steady_start else 'dont_walk_steady',
                       display_illuminated=True)
            values.append(row)
        write_rows(folder / 'steady-samples.jsonl', values)
        measured = measure(folder / 'steady-samples.jsonl', folder / 'steady-context.json')
        if measured['entry_relative_to_steady'] != expected:
            raise RuntimeError('Steady controlled relation missed')
        (folder / 'source-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        negatives = []
        for label, expected_error in (
            ('missing', 'Missing required source: steady-samples.jsonl'),
            ('reversed', 'Steady indication reversed'),
            ('wrong-governance', 'Steady source governing direction not established'),
            ('bad-footprint', 'Steady pedestrian pose/footprint differs'),
        ):
            damaged = root / (suffix + '-' + label)
            shutil.copytree(folder, damaged)
            (damaged / 'source-measurement.json').unlink()
            if label == 'missing':
                (damaged / 'steady-samples.jsonl').unlink()
            elif label == 'wrong-governance':
                wrong = dict(context)
                wrong['device_faces_pedestrian'] = False
                (damaged / 'steady-context.json').write_text(json.dumps(wrong) + '\n')
            else:
                wrong = [dict(value) for value in values]
                if label == 'reversed':
                    wrong[-1]['indication'] = 'walk'
                else:
                    wrong[10] = dict(wrong[10])
                    wrong[10]['pedestrian_footprint_xy_m'] = [list(v) for v in wrong[10]['pedestrian_footprint_xy_m']]
                    wrong[10]['pedestrian_footprint_xy_m'][0][0] += 1
                write_rows(damaged / 'steady-samples.jsonl', wrong)
            try:
                measure(damaged / 'steady-samples.jsonl', damaged / 'steady-context.json')
            except ValueError as error:
                if expected_error not in str(error):
                    raise
                negatives.append(str(error))
            else:
                raise RuntimeError('Damaged steady source accepted: ' + label)
        records.append({'case_suffix': suffix,
                        'case_id': HERE.name + '__' + suffix,
                        'retained_positive': str(folder), 'steady_start_s': steady_start,
                        'entry_relative_to_steady': expected, 'frames': 240,
                        'source_hashes': measured['source_sha256'],
                        'source_measurement_sha256': sha(folder / 'source-measurement.json'),
                        'negative_errors': negatives,
                        'scope': 'synthetic timing, unselected and unaccepted'})
    (HERE / 'steady-summary.json').write_text(json.dumps({
        'format': 'c10316-steady-synthetic-proof-v1', 'retained_root': str(root),
        'records': records}, indent=2) + '\n')
    print(json.dumps({'controlled_cases': 2, 'frames_per_case': 240,
                      'negative_rejections': 8, 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
