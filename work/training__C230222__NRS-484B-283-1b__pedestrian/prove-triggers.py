"""Retain synthetic source fixtures for all three curb fallback decisions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from triggers import decide, measure_source, sha


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def make_visibility(folder, rows, hidden=40):
    payload = {'source_kind': 'synthetic_visibility_fixture',
               'curb_samples_sha256': sha(folder / 'curb-samples.jsonl'),
               'frames': [{'native_frame': row['native_frame'], 'time_s': row['time_s'],
                           'curb_visible': True, 'vehicle_visible': i >= hidden}
                          for i, row in enumerate(rows)]}
    (folder / 'visibility.json').write_text(json.dumps(payload, indent=2) + '\n')


def main():
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c230222-triggers-'))
    records = []
    source_records = json.loads((HERE / 'curb-summary.json').read_text())['records']
    for source in source_records:
        suffix = source['case_suffix']
        source_dir = Path(source['retained_positive'])
        baseline = root / suffix / 'positive'
        baseline.mkdir(parents=True)
        for name in ('curb-samples.jsonl', 'curb-context.json'):
            shutil.copy2(source_dir / name, baseline / name)
        rows = [json.loads(line) for line in (baseline / 'curb-samples.jsonl').read_text().splitlines()]
        make_visibility(baseline, rows)
        measured = measure_source(baseline, baseline / 'visibility.json')
        decision = decide(suffix, measured)
        if decision['activated_fallbacks'] != ['fallback1', 'fallback2', 'fallback3']:
            raise RuntimeError('Synthetic positive did not activate all fallbacks')
        negatives = {}
        for ident in ('fallback1', 'fallback2', 'fallback3'):
            folder = root / suffix / ident
            shutil.copytree(baseline, folder)
            changed = json.loads(json.dumps(rows))
            if ident == 'fallback1':
                for row in changed:
                    row['pedestrian_xy_m'][0] -= 2
                    for point in row['pedestrian_footprint_xy_m']:
                        point[0] -= 2
                write_rows(folder / 'curb-samples.jsonl', changed)
                make_visibility(folder, changed)
            elif ident == 'fallback2':
                first = next(i for i, row in enumerate(changed) if row['pedestrian_speed_mps'] > 0)
                changed[first]['pedestrian_speed_mps'] = .1
                write_rows(folder / 'curb-samples.jsonl', changed)
                make_visibility(folder, changed)
            else:
                make_visibility(folder, changed, hidden=0)
            measured_negative = measure_source(folder, folder / 'visibility.json')
            result = decide(suffix, measured_negative)
            if result['decisions'][ident]['activate']:
                raise RuntimeError('Synthetic negative failed: ' + ident)
            negatives[ident] = {'folder': str(folder),
                'source_sha256': measured_negative['source_sha256'],
                'value': result['decisions'][ident]['value']}
        invalid = root / suffix / 'bad-join'
        shutil.copytree(baseline, invalid)
        payload = json.loads((invalid / 'visibility.json').read_text())
        payload['frames'][30]['native_frame'] += 1
        (invalid / 'visibility.json').write_text(json.dumps(payload) + '\n')
        try:
            measure_source(invalid, invalid / 'visibility.json')
        except ValueError as error:
            if 'frame join' not in str(error):
                raise
        else:
            raise RuntimeError('Bad visibility frame join accepted')
        records.append({'case_suffix': suffix, 'positive_folder': str(baseline),
                        'positive_source_sha256': measured['source_sha256'],
                        'positive_metrics': measured, 'positive_decision': decision,
                        'negative_fixtures': negatives,
                        'bad_join_folder': str(invalid), 'bad_join_rejected': True})
    summary = {'format': 'c230222-synthetic-trigger-proof-v1', 'records': records,
               'physical_trigger_observations': 0,
               'scope': 'Source-bound synthetic trigger logic only; visibility booleans are not original pixels.'}
    (HERE / 'trigger-proof-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'cases': 2, 'fallback_positive_decisions': 6,
                      'fallback_negative_decisions': 6, 'bad_frame_joins_rejected': 2,
                      'physical_trigger_observations': 0}))


if __name__ == '__main__':
    main()
