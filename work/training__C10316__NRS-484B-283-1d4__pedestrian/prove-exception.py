"""Unselected synthetic prior-entry indication pair for the d4 exception branch."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WITNESS = json.loads((HERE / 'steady-summary.json').read_text())['records'][0]
SOURCE = Path(WITNESS['retained_positive'])
sys.path.insert(0, str(HERE / 'native'))
from exception import measure, sha


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-prior-entry-'))
    base = [json.loads(line) for line in (SOURCE / 'steady-samples.jsonl').read_text().splitlines()]
    context_base = json.loads((SOURCE / 'steady-context.json').read_text())
    assert len(base) == 240
    records = []
    for suffix, expected in (('exception_1_1', 'dont_walk_flashing'),
                             ('exception_1_2', 'walk')):
        folder = root / suffix
        folder.mkdir()
        shutil.copy2(SOURCE / 'road.xodr', folder / 'road.xodr')
        context = dict(context_base)
        context.update(authored_map_sha256=sha(folder / 'road.xodr'),
                       countdown_present=False, steady_start_s=4.0,
                       exception_source_comparison='first_entry_indication_only',
                       lawful_prior_entry_review='unverified',
                       introductory_exceptions='unreviewed_synthetic_context')
        (folder / 'exception-context.json').write_text(json.dumps(context, indent=2) + '\n')
        rows = []
        for index, original in enumerate(base):
            row = dict(original)
            time = index / 20
            if time >= 4:
                indication, lit = 'dont_walk_steady', True
            elif suffix == 'exception_1_1' and time >= .5:
                indication, lit = 'dont_walk_flashing', (index // 5) % 2 == 0
            else:
                indication, lit = 'walk', True
            row.update(indication=indication, display_illuminated=lit,
                       countdown_visible=False)
            rows.append(row)
        write_rows(folder / 'exception-samples.jsonl', rows)
        measured = measure(folder / 'exception-samples.jsonl', folder / 'exception-context.json')
        if measured['entry_indication'] != expected or measured['post_steady_crossing_samples'] != 80:
            raise RuntimeError('Prior-entry source missed expected controlled fact')
        (folder / 'source-measurement.json').write_text(json.dumps(measured, indent=2) + '\n')
        if not measured['progress_bound']['engineering_surrogate_met']:
            raise RuntimeError('Continuous synthetic crossing missed declared progress bound')
        paused = root / (suffix + '-paused')
        shutil.copytree(folder, paused)
        paused_rows = [dict(row) for row in rows]
        for index in range(100, 108):
            paused_rows[index]['pedestrian_xy_m'] = list(rows[99]['pedestrian_xy_m'])
            paused_rows[index]['pedestrian_footprint_xy_m'] = [list(v) for v in rows[99]['pedestrian_footprint_xy_m']]
        write_rows(paused / 'exception-samples.jsonl', paused_rows)
        paused_measurement = measure(paused / 'exception-samples.jsonl', paused / 'exception-context.json')
        if (paused_measurement['progress_bound']['engineering_surrogate_met'] or
                paused_measurement['progress_bound']['observed_max_stationary_s'] < .35 or
                paused_measurement['legal_verdict_claimed']):
            raise RuntimeError('Paused synthetic crossing did not expose engineering-bound failure')
        (paused / 'source-measurement.json').write_text(json.dumps(paused_measurement, indent=2) + '\n')
        negatives = []
        for label, expected_error in (
            ('missing', 'Missing required source: exception-samples.jsonl'),
            ('unexpected-countdown', 'Prior-entry unexpected countdown'),
            ('wrong-governance', 'Prior-entry governing direction not established'),
            ('reversed', 'Prior-entry phase sequence invalid'),
            ('bad-footprint', 'Prior-entry pedestrian pose/footprint differs'),
        ):
            bad = root / (suffix + '-' + label)
            shutil.copytree(folder, bad)
            (bad / 'source-measurement.json').unlink()
            if label == 'missing':
                (bad / 'exception-samples.jsonl').unlink()
            elif label == 'wrong-governance':
                changed = dict(context)
                changed['device_faces_pedestrian'] = False
                (bad / 'exception-context.json').write_text(json.dumps(changed) + '\n')
            else:
                damaged = [dict(row) for row in rows]
                if label == 'unexpected-countdown':
                    damaged[10]['displayed_countdown_s'] = 3
                elif label == 'reversed':
                    damaged[-1]['indication'] = 'walk'
                else:
                    damaged[10]['pedestrian_footprint_xy_m'] = [list(v) for v in damaged[10]['pedestrian_footprint_xy_m']]
                    damaged[10]['pedestrian_footprint_xy_m'][0][0] += 1
                write_rows(bad / 'exception-samples.jsonl', damaged)
            try:
                measure(bad / 'exception-samples.jsonl', bad / 'exception-context.json')
            except ValueError as error:
                if expected_error not in str(error):
                    raise
                negatives.append(str(error))
            else:
                raise RuntimeError('Damaged prior-entry source accepted: ' + label)
        records.append({'case_suffix': suffix, 'case_id': HERE.name + '__' + suffix,
                        'retained_positive': str(folder), 'entry_indication': expected,
                        'steady_start_s': 4.0, 'frames': 240,
                        'source_hashes': measured['source_sha256'],
                        'source_measurement_sha256': sha(folder / 'source-measurement.json'),
                        'paused_diagnostic': str(paused),
                        'paused_source_measurement_sha256': sha(paused / 'source-measurement.json'),
                        'negative_errors': negatives,
                        'scope': 'synthetic prior-entry source facts, not lawful-entry or legal verdict'})
    (HERE / 'exception-summary.json').write_text(json.dumps({
        'format': 'c10316-prior-entry-synthetic-proof-v1', 'retained_root': str(root),
        'records': records}, indent=2) + '\n')
    print(json.dumps({'exception_cases': 2, 'frames_per_case': 240,
                      'negative_rejections': 10, 'progress_bound_negative_metrics': 2,
                      'lawful_prior_entry_proven': False,
                      'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
