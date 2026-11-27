"""Exercise the selected criterion through the pinned runtime assessor."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def run() -> None:
    scratch = REPO / '.runtime-work/c143766-1d3-owner-nov26/runtime-physical'
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cfg = json.loads((ROOT / 'cases/walk_facing_yield/config.json').read_text())
    write(scratch / 'config.json', cfg)
    mapping = [{'video_frame': i, 'carla_frame': i + 1, 'time_s': .05 * (i + 1)}
               for i in range(3)]
    (scratch / 'video_frames.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in mapping))
    observed = {}
    for kind, positions, expected in (
            ('complete', (0., 3., 8.), 'met'),
            ('incomplete', (0., 1., 2.), 'not_met')):
        rows = [{'frame': i + 1, 'time_s': .05 * (i + 1),
                 'position_m': [x, 0., 0.]} for i, x in enumerate(positions)]
        (scratch / 'trace.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        result = assess_physical(scratch, cfg)
        actual = result['physical_checks']['maneuver']['status']
        if actual != expected:
            raise ValueError(f'{kind}: {actual} != {expected}')
        observed[kind] = actual
    (scratch / 'trace.jsonl').unlink()
    result = assess_physical(scratch, cfg)
    observed['missing'] = result['physical_checks']['maneuver']['status']
    if observed['missing'] != 'unverified':
        raise ValueError('Missing original motion was not unverified')
    receipt = {'runtime_criterion': cfg['physical_completion']['criterion'],
               'config_sha256': hashlib.sha256((ROOT / 'cases/walk_facing_yield/config.json').read_bytes()).hexdigest(),
               'status_by_fixture': observed,
               'scope': 'synthetic current-runtime protocol; original CARLA motion pending'}
    write(ROOT / 'cpu-runtime-physical-proof.json', receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/nonexistent')).resolve()
    if REPO / '.runtime-work' not in output_root.parents:
        raise ValueError('Set output root under .runtime-work before runtime import')
    run()
