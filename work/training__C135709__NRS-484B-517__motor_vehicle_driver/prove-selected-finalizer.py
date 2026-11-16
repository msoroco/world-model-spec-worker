"""Exercise selected saved finalizer with retained synthetic sources and missing review."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'native'))
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
import fixture_raw
import finalize_selected
from worker_exchange.measurement_contract import validate, verify_report


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def prove_one(witness, candidate, base):
    construction_path = ROOT/'selected-all'/witness/candidate/'construction.json'
    construction = json.loads(construction_path.read_text())
    attempt = base/witness/candidate
    attempt.mkdir(parents=True)
    (attempt/'construction.json').write_bytes(construction_path.read_bytes())
    for item in construction['files']:
        path = attempt/item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    raw = base/'raw'/witness/candidate
    raw.parent.mkdir(parents=True, exist_ok=True)
    fixture_raw.generate(attempt, raw)
    for path in raw.iterdir():
        shutil.copy2(path, attempt/path.name)
    actors = [json.loads(line) for line in (attempt/'native-raw-actors.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    for row in mapping:
        row['carla_frame'] = row['native_frame']
    write_rows(attempt/'video_frames.jsonl', mapping)
    write_rows(attempt/'trace.jsonl', [
        {'frame': row['native_frame'], 'time_s': row['time_s'],
         'position': dict(zip(('x', 'y', 'z'), row['ego']['center_native_xyz_m'])),
         'position_m': row['ego']['center_native_xyz_m'],
         'heading_deg': row['ego']['yaw_deg'],
         'speed_mps': row['ego']['speed_mps']}
        for row in actors])
    report = finalize_selected.finalize(attempt, attempt/'analysis-report.json')
    contract = json.loads((ROOT/'selected-measurement-contracts'/
                           (witness+'.json')).read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    validate(contract, plan['requirement_dispositions'],
             (ROOT/'native/finalize_selected.py').read_text(), construction['case_id'])
    verify_report(contract, report, attempt)
    occupied = report['measurements']['sampled_stand_occupancy_frames']['value']
    assert occupied == 0 if witness == 'reference' else occupied >= 30
    assert len(list((attempt/'channels').glob('*.jsonl'))) == 4
    negative = base/'negative'/witness/candidate
    negative.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(attempt, negative, ignore=shutil.ignore_patterns(
        'result.json', 'analysis-report.json', 'channels', 'stand-context.json'))
    (negative/'stand-review.jsonl').unlink()
    try:
        finalize_selected.finalize(negative, negative/'analysis-report.json')
    except ValueError as error:
        assert 'Missing required source: stand-review.jsonl' in str(error)
    else:
        raise AssertionError('Missing reviewed stand source was accepted')
    return {'case': witness, 'candidate': candidate,
            'occupied_frames': report['measurements']['sampled_stand_occupancy_frames']['value'],
            'missing_review_rejected': True}


def prove():
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',
                                     prefix='c135709-finalizer-') as temporary:
        base = Path(temporary)
        return [prove_one(witness, candidate, base)
                for witness in ('reference', 'contrast')
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')]


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
