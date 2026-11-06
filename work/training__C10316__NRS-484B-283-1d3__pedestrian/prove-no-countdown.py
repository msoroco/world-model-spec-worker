"""Two unselected synthetic Walk-versus-flashing-entry sources; no legal verdict."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work/c10316-countdown-3nc21fz5/probe_01'
sys.path.insert(0, str(HERE / 'native'))
from no_countdown import measure, signal_state, sha


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def main():
    if not SOURCE.is_dir():
        raise RuntimeError('Retained 240-frame synthetic pedestrian path missing')
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-no-countdown-'))
    base = [json.loads(line) for line in (SOURCE / 'countdown_samples.jsonl').read_text().splitlines()]
    context_base = json.loads((SOURCE / 'countdown-context.json').read_text())
    assert len(base) == 240
    records = []
    for suffix, flash_start, expected in (('controlled_1', 2, 'walk'),
                                          ('controlled_2', .5, 'dont_walk_flashing')):
        folder = root / suffix
        folder.mkdir()
        shutil.copy2(HERE / 'native/road.xodr', folder / 'road.xodr')
        context = dict(context_base)
        context.update(authored_map_sha256=sha(folder / 'road.xodr'),
                       source_kind='synthetic_scene_request',
                       countdown_present=False, flash_start_s=flash_start,
                       steady_start_s=9, lawful_prior_entry_review='unverified',
                       introductory_exceptions='unreviewed_synthetic_context')
        (folder / 'no-countdown-context.json').write_text(json.dumps(context, indent=2) + '\n')
        values = []
        for index, original in enumerate(base):
            state, illuminated = signal_state(index, flash_start)
            row = {k: v for k, v in original.items() if k not in
                   ('displayed_countdown_s', 'indication', 'display_illuminated')}
            row.update(indication=state, display_illuminated=illuminated,
                       countdown_visible=False)
            values.append(row)
        write_rows(folder / 'no-countdown-samples.jsonl', values)
        report = measure(folder / 'no-countdown-samples.jsonl', folder / 'no-countdown-context.json')
        if report['entry_indication'] != expected or not report['clearance_before_steady']:
            raise RuntimeError('No-countdown controlled source missed requested timing')
        (folder / 'analysis-report.json').write_text(json.dumps(report, indent=2) + '\n')
        negatives = []
        missing = root / (suffix + '-missing')
        missing.mkdir()
        shutil.copy2(folder / 'no-countdown-context.json', missing / 'no-countdown-context.json')
        shutil.copy2(folder / 'road.xodr', missing / 'road.xodr')
        try:
            measure(missing / 'no-countdown-samples.jsonl', missing / 'no-countdown-context.json')
        except ValueError as error:
            if 'Missing required source: no-countdown-samples.jsonl' not in str(error):
                raise
            negatives.append(str(error))
        else:
            raise RuntimeError('Missing no-countdown source accepted')
        for label, mutate, expected_error in (
            ('unexpected-countdown', lambda r: r.update(displayed_countdown_s=3),
             'Countdown absent condition not established'),
            ('wrong-governance', None, 'Governing pedestrian direction not established'),
        ):
            damaged = root / (suffix + '-' + label)
            shutil.copytree(folder, damaged)
            (damaged / 'analysis-report.json').unlink()
            if mutate:
                rows = [dict(item) for item in values]
                mutate(rows[10])
                write_rows(damaged / 'no-countdown-samples.jsonl', rows)
            else:
                bad = dict(context)
                bad['device_faces_pedestrian'] = False
                (damaged / 'no-countdown-context.json').write_text(json.dumps(bad) + '\n')
            try:
                measure(damaged / 'no-countdown-samples.jsonl', damaged / 'no-countdown-context.json')
            except ValueError as error:
                if expected_error not in str(error):
                    raise
                negatives.append(str(error))
            else:
                raise RuntimeError('Damaged no-countdown source accepted: ' + label)
        records.append({'case_suffix': suffix, 'case_id': 'training__C10316__NRS-484B-283-1d3__pedestrian__' + suffix,
                        'retained_positive': str(folder), 'flash_start_s': flash_start,
                        'entry_indication': expected, 'frames': 240,
                        'source_hashes': report['source_sha256'], 'analysis_report_sha256': sha(folder / 'analysis-report.json'),
                        'negative_errors': negatives, 'scope': 'synthetic timing, unselected and unaccepted'})
    (HERE / 'no-countdown-summary.json').write_text(json.dumps({
        'format': 'c10316-no-countdown-synthetic-proof-v1', 'retained_root': str(root),
        'records': records}, indent=2) + '\n')
    print(json.dumps({'controlled_cases': 2, 'frames_per_case': 240,
                      'negative_rejections': 6, 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
