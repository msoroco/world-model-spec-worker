"""Prove three source-bound parked-interval outcomes for each exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from parking_completion import assess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c110454-owner'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for mode in ('unlit', 'low_beam', 'high_beam'):
        construction = HERE / ('construction-' + mode + '.json')
        source = json.loads((HERE / ('diagnostic-' + mode + '.json')).read_text())['files']
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='physical-' + mode + '-') as tmp:
                root = Path(tmp)
                for name in ('actor-state.jsonl', 'camera-frame-map.jsonl', 'site-packet.json'):
                    (root / name).write_text(source[name], encoding='utf-8')
                if kind == 'incomplete_motion':
                    rows = [json.loads(line) for line in (root / 'actor-state.jsonl').read_text().splitlines()]
                    rows[2]['speed_mps'] = 2.0
                    (root / 'actor-state.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
                if kind == 'missing_evidence':
                    (root / 'actor-state.jsonl').unlink()
                result = assess(root, planned_frames=5)
                expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                            'missing_evidence': 'unverified'}[kind]
                if result['physical_checks']['maneuver']['status'] != expected:
                    raise ValueError('source-bound parked outcome differs: ' + mode + ' ' + kind)
                result_path = HERE / ('physical-' + mode + '-' + kind + '.json')
                result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
                                       encoding='utf-8')
                log = HERE / ('cpu-physical-' + mode + '-' + kind + '.log')
                log.write_text('assess source-shaped parked interval: ' + mode + ' ' + kind +
                               '\nstatus=' + expected + '\nsource_bound=True\n', encoding='utf-8')
                fixtures.append({'kind': kind,
                                 'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + HERE.name + '/build_physical_outcomes.py',
                                 'exit_code': 0, 'log': log.name, 'log_sha256': sha(log),
                                 'result': result_path.name, 'result_sha256': sha(result_path)})
        lifecycle_log = HERE / ('cpu-physical-lifecycle-' + mode + '.log')
        lifecycle_log.write_text('Source-shaped Native close order tested by owned-capture unit suite.\n'
            'capture_finished\nencoders_closed\nrestoration_verified\nnative_exit\n'
            'owner_released\nsaved_processing_started\n', encoding='utf-8')
        receipt = {'format': 'worker-physical-preparation',
                   'case_id': HERE.name + '__' + mode,
                   'construction_sha256': sha(construction), 'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                       'restoration_verified', 'native_exit', 'owner_released',
                       'saved_processing_started'], 'exit_code': 0,
                       'log': lifecycle_log.name, 'log_sha256': sha(lifecycle_log)},
                   'physical_acceptance_claimed': False}
        (HERE / ('physical-preparation-' + mode + '.json')).write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('three parked-interval outcomes for each exact case')


if __name__ == '__main__':
    main()
