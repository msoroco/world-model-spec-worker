"""Test independent retained-source comparison and four source mutations."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from comparison_audit import audit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work'
NAMES = ('geometry.json', 'signal.json', 'native-rows.jsonl', 'native-index.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(source, target):
    target.mkdir()
    for name in NAMES:
        shutil.copy2(source / name, target / name)


def reindex(target, name):
    index = json.loads((target / 'native-index.json').read_text())
    index['files'][name] = sha(target / name)
    (target / 'native-index.json').write_text(json.dumps(index, indent=2) + '\n')


def rejected(halt, roll, expected):
    try:
        audit(halt, roll)
    except ValueError as error:
        if expected in str(error):
            return str(error)
        raise
    raise AssertionError('expected rejection: ' + expected)


def main():
    source_a = REPO / '.runtime-work/c111277-compat-new-a-primary'
    source_b = REPO / '.runtime-work/c111277-compat-new-b-primary'
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='c111277-comparison-') as directory:
        root = Path(directory)
        halt, roll = root / 'halt', root / 'roll'
        snapshot(source_a, halt)
        snapshot(source_b, roll)
        positive = audit(halt, roll)
        missing = root / 'missing'
        shutil.copytree(halt, missing)
        (missing / 'signal.json').unlink()
        missing_error = rejected(missing, roll, 'missing signal.json')
        changed = root / 'changed'
        shutil.copytree(halt, changed)
        with (changed / 'native-rows.jsonl').open('a') as stream:
            stream.write('\n')
        hash_error = rejected(changed, roll, 'source hash mismatch: native-rows.jsonl')
        no_contrast_error = rejected(roll, roll, 'comparison condition identities changed')
        fixed = root / 'fixed'
        shutil.copytree(halt, fixed)
        geometry = json.loads((fixed / 'geometry.json').read_text())
        geometry['crosswalk_near_edge_x_m'] -= 1
        (fixed / 'geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
        reindex(fixed, 'geometry.json')
        fixed_error = rejected(fixed, roll, 'fixed geometry or signal differs')
        measured = root / 'measured'
        shutil.copytree(halt, measured)
        rows = [json.loads(s) for s in (measured / 'native-rows.jsonl').read_text().splitlines()]
        for row in rows:
            if row['ego_speed_mps'] <= .05:
                row['ego_speed_mps'] = 1.0
        (measured / 'native-rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        reindex(measured, 'native-rows.jsonl')
        measurement_error = rejected(measured, roll, 'halt contrast absent')
    report = {'format': 'nrs-484b-250-4-comparison-audit-proof-v2',
              'passed': True, 'positive': positive,
              'negative_rejections': [missing_error, hash_error, no_contrast_error,
                                      fixed_error, measurement_error],
              'original_native_observed': False}
    target = ROOT / 'proofs/comparison-audit-proof.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'negative_checks': 5}))


if __name__ == '__main__':
    main()
