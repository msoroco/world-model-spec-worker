"""Copy pinned diagnostic receipts into the selected, exact-case manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT = REPO / '.runtime-work/c110264-output'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(source: Path, destination: Path) -> None:
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text('\n'.join(lines) + ('\n' if lines else ''))


def main() -> None:
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        for candidate_id in ('primary', 'fallback1'):
            base = ('compat-left_signal-v2' if suffix == 'left_signal' and candidate_id == 'primary'
                    else f'compat-{suffix}-{candidate_id}-v2')
            output = OUTPUT / base
            source = json.loads((output / 'compatibility.json').read_text())
            assert source['passed'] is True
            name = f'compat-{suffix}-{candidate_id}'
            receipt_path = HERE / f'{name}.json'
            log_path = HERE / f'cpu-{name}-analysis.log'
            negative_path = HERE / f'cpu-{name}-negative.log'
            clean_log(output / 'compatibility-analysis.log', log_path)
            clean_log(output / 'negative-analysis.log', negative_path)
            source['log_sha256'] = digest(log_path)
            source['negative_log_sha256'] = digest(negative_path)
            receipt_path.write_text(json.dumps(source, indent=2) + '\n')
            spec = {'receipt': receipt_path.name, 'sha256': digest(receipt_path),
                    'log': log_path.name, 'negative_log': negative_path.name}
            if candidate_id == 'primary':
                entry['compatibility'] = spec
            else:
                entry['candidates'][0]['compatibility'] = spec
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
