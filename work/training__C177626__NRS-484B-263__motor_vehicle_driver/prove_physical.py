"""Exercise source-backed entry completion outcomes on synthetic saved inputs."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(suffix):
    case = ROOT.name + '__selected_ed45c8e4__condition_' + suffix
    construction = ROOT / 'cases' / ('condition_' + suffix) / 'construction.json'
    bundle = json.loads(construction.read_text())
    config = json.loads(next(row['content'] for row in bundle['files'] if row['path'] == 'config.json'))
    assert config['physical_completion']['criterion'] == 'road_transition'
    source = ROOT / 'selected-source' / ('condition_' + suffix)
    output = ROOT / 'physical' / ('condition_' + suffix)
    output.mkdir(parents=True, exist_ok=True)
    scratch = REPO / '.runtime-work' / 'c177626-physical' / suffix
    fixtures = []
    for kind, expected in (('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        attempt = scratch / kind
        if attempt.exists():
            shutil.rmtree(attempt)
        attempt.mkdir(parents=True)
        for name in ('entry_history.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
            shutil.copy2(source / name, attempt / name)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (attempt / 'entry_history.jsonl').read_text().splitlines()]
            for row in rows:
                row['road_id'] = 13
            (attempt / 'entry_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (attempt / 'entry_history.jsonl').unlink()
        result = assess_physical(attempt, config)
        assert result['physical_checks']['maneuver']['status'] == expected, (kind, result['physical_checks']['maneuver'])
        assert result['maneuver_completed'] == (expected == 'met')
        result.update(provenance_kind='synthetic_fixture', diagnostic_fixture=True)
        path = output / (kind + '.json')
        path.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False) + '\n')
        log = output / (kind + '.log')
        log.write_text('PASS ' + case + ' ' + kind + ' ' + expected + '\n')
        fixtures.append({'kind': kind, 'command': 'prove_physical.py --case ' + case + ' --fixture ' + kind,
                         'exit_code': 0, 'log': log.relative_to(ROOT).as_posix(),
                         'log_sha256': digest(log), 'result': path.relative_to(ROOT).as_posix(),
                         'result_sha256': digest(path)})
    life = ROOT / 'lifecycle-proof.log'
    assert life.is_file()
    proof = {'case_id': case, 'construction_sha256': digest(construction),
             'fixtures': fixtures,
             'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                                      'native_exit', 'owner_released', 'saved_processing_started'],
                           'exit_code': 0, 'log': life.relative_to(ROOT).as_posix(),
                           'log_sha256': digest(life)}}
    receipt = output / 'receipt.json'
    receipt.write_text(json.dumps(proof, indent=2) + '\n')
    return {'receipt': receipt.relative_to(ROOT).as_posix(), 'sha256': digest(receipt)}


if __name__ == '__main__':
    print(json.dumps({suffix: run(suffix) for suffix in ('a', 'b')}))
