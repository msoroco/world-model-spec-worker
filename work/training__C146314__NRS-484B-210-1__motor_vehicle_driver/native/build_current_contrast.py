"""Build the unselected 30-second obstruction contrast for paragraph (d)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'current-contrast'
CASE_ID = HERE.parent.name + '__witness_2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    source = HERE / 'current-primary'
    if not (source / 'construction.json').is_file():
        raise FileNotFoundError('Build the source-bound primary draft first')
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('one-way-pass.xodr', 'assignment-source.json', 'case-plan.json',
                 'capture.py'):
        (OUT / name).write_bytes((source / name).read_bytes())
    (OUT / 'saved.py').write_bytes((HERE / 'current_contrast_saved.py').read_bytes())
    rows = []
    for line in (source / 'requested-tracks.jsonl').read_text().splitlines():
        row = json.loads(line)
        row['case_id'] = CASE_ID
        row['right_lane_obstruction_requested'] = True
        row['obstruction_x_m'] = 55.0
        row['obstruction_y_m'] = -6.8
        row['obstruction_significance_verified'] = False
        rows.append(row)
    (OUT / 'requested-tracks.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))
    config = json.loads((source / 'config.json').read_text())
    config.update(case_id=CASE_ID, tracks_sha256=sha(OUT / 'requested-tracks.jsonl'),
                  right_lane_obstruction_requested=True,
                  obstruction_x_m=55.0, obstruction_y_m=-6.8,
                  obstruction_significance_verified=False,
                  status='unselected_cpu_diagnostic')
    put(OUT / 'config.json', config)
    checker = (source / 'check.py').read_text().replace('__witness_1', '__witness_2')
    checker = checker.replace("    return {'case_id': cfg['case_id']", "    if not (cfg.get('right_lane_obstruction_requested') is True and\n"
        "            cfg.get('obstruction_x_m') == 55.0 and\n"
        "            cfg.get('obstruction_y_m') == -6.8 and\n"
        "            all(json.loads(line).get('right_lane_obstruction_requested') is True and\n"
        "                json.loads(line).get('obstruction_x_m') == 55.0 and\n"
        "                json.loads(line).get('obstruction_y_m') == -6.8 and\n"
        "                json.loads(line).get('obstruction_significance_verified') is False\n"
        "                for line in lines)):\n"
        "        raise ValueError('Requested obstruction differs')\n"
        "    return {'case_id': cfg['case_id']")
    (OUT / 'check.py').write_text(checker)
    tests = OUT / 'tests'
    tests.mkdir(exist_ok=True)
    (tests / 'test_exact.py').write_bytes((HERE / 'current_contrast_test.py').read_bytes())
    files = ['config.json', 'requested-tracks.jsonl', 'one-way-pass.xodr',
             'assignment-source.json', 'case-plan.json', 'check.py', 'capture.py',
             'saved.py', 'tests/test_exact.py']
    construction = {'case_id': CASE_ID, 'cell_id': 'C146314',
        'law_id': 'NRS-484B-210-1', 'actor': 'motor_vehicle_driver',
        'entrypoint': 'capture.py', 'status': 'unselected_cpu_diagnostic',
        'recording_description': 'Requested right pass beside an authored curb cone on a one-way two-lane road; obstruction significance, original motion and pixels remain unverified.',
        'files': [{'path': name, 'content': (OUT / name).read_text()} for name in files]}
    put(OUT / 'construction.json', construction)
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': HERE.parent.name, 'status': 'draft_not_selected',
        'cases': [{'case_id': CASE_ID, 'construction': 'construction.json',
            'construction_sha256': sha(OUT / 'construction.json'),
            'candidates': [], 'candidate_risk': {'status': 'physical',
                'reason': 'Cone significance, full right pass, road designation and original pixels are unverified.'}}],
        'original_native_observed': False, 'delivery_ready': False}
    put(OUT / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases']), 'frames': 600, 'cameras': 4}))
