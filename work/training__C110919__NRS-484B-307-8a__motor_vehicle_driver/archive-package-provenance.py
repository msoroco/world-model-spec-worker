"""Retain small, hashed synthetic package outputs for independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = {
    'geometry': 'fixture/road_geometry.json',
    'capture_manifest': 'fixture/capture/manifest.json',
    'result': 'output/result.json',
    'analysis': 'output/analysis-report.json',
    'finalizer': 'output/finalize.py',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive() -> dict:
    summary = json.loads((HERE/'package-probes-summary.json').read_text())
    if len(summary['results']) != 8 or any(row['exit_code'] for row in summary['results']):
        raise ValueError('Eight successful package probes required')
    rows = []
    for row in summary['results']:
        case, candidate = row['case'], row['candidate']
        log = HERE/row['log']
        first = log.read_text().splitlines()[0]
        if not first.startswith('scratch '):
            raise ValueError('Package scratch location absent')
        scratch = Path(first.removeprefix('scratch ')).resolve()
        if scratch.parent != (ROOT/'.runtime-work').resolve() or not scratch.name.startswith('c110919-package-'):
            raise ValueError('Package scratch location differs')
        destination = HERE/'native/package-provenance'/case/candidate
        destination.mkdir(parents=True, exist_ok=True)
        files = {}
        for key, relative in SOURCES.items():
            source = scratch/relative
            if not source.is_file():
                raise ValueError('Package source missing: '+relative)
            target = destination/(key + source.suffix)
            shutil.copyfile(source, target)
            files[key] = {'path': str(target.relative_to(HERE)), 'sha256': sha(target)}
        rows.append({'case': case, 'candidate': candidate,
                     'package_log_sha256': sha(log), 'files': files})
    output = {'format': 'c110919-synthetic-package-provenance-v1',
              'assignment_id': HERE.name, 'results': rows,
              'scope': 'retained diagnostic CPU package bytes; no Native execution or acceptance'}
    (HERE/'native/package-provenance-index.json').write_text(json.dumps(output, indent=2)+'\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'archived': len(archive()['results'])}))
